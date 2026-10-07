"""Telegram UI; uncertain tickets require confirmation before storage."""
import asyncio
import logging
import os
import re
import time
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from accounting import Ledger, summary
from workspace import WorkspaceLedger, telegram_id, user_ids
from presentation import render_summary, render_book
from results import fetch_latest_result, ResultError, VN_TIMEZONE
from calculator import propose_b_choice

logging.basicConfig(level=logging.WARNING)
logging.getLogger('httpx').setLevel(logging.WARNING)
MENU_ROWS=[['Nhập tin','Xem tổng'],['Đổi người','Sổ vé'],['Nợ cũ','Xem raw'],['Tạo người','Sửa %','Sửa thưởng'],['Xiên ×14','Xiên ×15'],['Đổi ngày','Sửa tin','Xóa tin'],['Hủy']]
MENU=ReplyKeyboardMarkup(MENU_ROWS,resize_keyboard=True,is_persistent=True)
DB=WorkspaceLedger(os.getenv('BOT_DB','data.sqlite3'))
OWNER_MENU=ReplyKeyboardMarkup(MENU_ROWS+[['👥 Người sử dụng']],resize_keyboard=True,is_persistent=True)
USER_MENU=ReplyKeyboardMarkup([['➕ Thêm người','➖ Xóa người'],['📋 Danh sách','↩️ Quay lại']],resize_keyboard=True)
USER_ACTIONS={'👥 Người sử dụng','➕ Thêm người','➖ Xóa người','📋 Danh sách','↩️ Quay lại','XÓA QUYỀN'}
B_MENU=ReplyKeyboardMarkup([['BAO TOÀN BỘ','ĐỀ BỘ'],['Hủy']],resize_keyboard=True)
NAVIGATION={'Nhập tin','Xem tổng','Đổi người','Danh sách tin','Tạo người','Sửa %','Sửa thưởng',
            'Xiên ×14','Xiên ×15','Đổi ngày','Sửa tin','Xóa tin','Hủy','Nợ cũ','Xem raw','Sổ vé'} | (USER_ACTIONS-{'XÓA QUYỀN'})

def clear_pending(context):
    for key in ('state','pending_b','delete_id','delete_context','edit_revisions','delete_revision','remove_users'):
        context.user_data.pop(key,None)

def workspace_owner():return telegram_id(os.getenv('TELEGRAM_ADMIN_ID',''))

def allowed(update):
    try:
        return (update.effective_chat.type=='private' and
                DB.authorized(workspace_owner(),update.effective_user.id))
    except ValueError:return False

def is_owner(update):return update.effective_user.id==workspace_owner()

def shared_day(update,context):
    initial=context.user_data.get('day',today())
    day=DB.day(workspace_owner(),update.effective_user.id,initial)
    changed=initial!=day
    if changed:clear_pending(context)
    context.user_data['day']=day
    return day,changed

async def show_users(update):
    owner=workspace_owner();ids=DB.users(owner,update.effective_user.id)
    await reply(update,'NGƯỜI ĐANG ĐƯỢC PHÉP DÙNG BOT\n\n👑 OWNER: '+str(owner)+'\n\n'+
                '\n'.join('✅ '+str(uid) for uid in ids)+'\n\nTổng: '+str(len(ids)+1)+' người',USER_MENU)

def today():return datetime.now(VN_TIMEZONE).strftime('%d-%m-%Y')
async def reply(update,text,markup=MENU):
    if not allowed(update):return
    if markup is MENU and is_owner(update):markup=OWNER_MENU
    for start in range(0,len(text),3500):
        if not allowed(update):return
        await update.effective_message.reply_text(text[start:start+3500],reply_markup=markup)

async def save_input(update,context,p,day,raw,message,tid=None):
    if tid is None and context.user_data.get('seen_profile')==p['id'] and context.user_data.get('seen_config')!=p['config']:
        context.user_data['seen_config']=p['config']
        clear_pending(context)
        await reply(update,'Tỷ lệ của bảng vừa được người khác đổi. Chưa lưu tin. Kiểm tra tỷ lệ dưới đây rồi gửi lại tin.\n'+card(p));return
    choice=propose_b_choice(raw)
    if choice:
        context.user_data['state']='b_choice'
        context.user_data['pending_b']={
            'bao':choice.bao_corrected,'bo':choice.bo_corrected,
            'profile':p['id'],'day':day,'message':message,'tid':tid,
            'config':p['config'],'expires':time.time()+300,
        }
        await reply(update,'B chưa rõ. Chưa lưu tin. Chọn một cách hiểu:\n'
                    +'BAO TOÀN BỘ:\n'+choice.bao_display+'\nĐỀ BỘ:\n'+choice.bo_display,B_MENU)
        return
    if tid is not None:
        DB.replace(workspace_owner(),p['id'],day,tid,raw,actor=update.effective_user.id,expected_revision=context.user_data.get('edit_revisions',{}).get(tid))
        clear_pending(context)
        await reply(update,'Đã sửa tin; giữ tỷ lệ gốc. Có lưu lịch sử sửa.')
        return
    fresh=DB.add(workspace_owner(),p['id'],day,message,raw,actor=update.effective_user.id,expected_config=p['config'])
    clear_pending(context)
    if not fresh:
        await reply(update,'Message ID đã ghi nhận trước đó; không lưu/cộng thêm, kể cả vé đã xóa.')
        return
    tid=DB.message_ticket(workspace_owner(),update.effective_user.id,message)
    await reply(update,f"Đã lưu — {p['name']} — {day}\nID: {tid}\nBấm Xem tổng để tính thưởng và thu/trả.")

def current(update,context):
    pid=context.user_data.get('profile')
    if not pid:raise ValueError('Bấm Nhập tin rồi chọn tên trước.')
    return DB.profile(workspace_owner(),pid,actor=update.effective_user.id)

def profile_input(raw):
    """Normalize only the create-person dialog, including legacy semicolons."""
    parts=raw.split(';',1) if ';' in raw else raw.split(None,1)
    if len(parts)!=2:raise ValueError('Gửi Khách HBX hoặc Chủ OK. Tên có thể có khoảng trắng.')
    side={'khách':'Khách','khach':'Khách','chủ':'Chủ','chu':'Chủ'}.get(parts[0].strip().casefold())
    if side is None:raise ValueError('Loại người phải là Khách hoặc Chủ.')
    return side,parts[1].strip()

def percent_input(raw):
    """Whitespace separates quick values; commas remain inside each number."""
    # Keep both existing configure separators intact; add no new separator.
    if ';' in raw or re.search(r'\s+-\s+',raw):return raw
    values=raw.split()
    if len(values)!=5:raise ValueError('Gửi đúng 5 số: Đề Bao Xiên 2 Xiên 3,4 Càng. Ví dụ: 5 3,5 18 21 38')
    return ';'.join(values)

def reward_input(raw):
    """Normalize only reward dialog separators; DB keeps all validation."""
    if ';' in raw or re.search(r'\s+-\s+',raw):return raw
    values=raw.split()
    if len(values)!=7:raise ValueError('Gửi đúng 7 số: Đề Bao Xiên 2 Xiên 3 Xiên 4 Càng Áp càng.')
    return ';'.join(values)

def card(p):
    cfg=p['config'];v=cfg.get('active','15');pc=cfg.get('variants',{}).get(v,cfg['percent'])
    return f"{p['name']} — {p['side']}\n"+'\n'.join(f'{k}: {pc[k]}% — thưởng ×'+(v if k=='Xiên 2' else cfg['reward'][k]) for k in ('Đề','Bao','Xiên 2','Xiên 3','Xiên 4','Càng'))+'\n% đang sửa thuộc bộ Xiên ×'+v+'; chỉ áp dụng cho tin mới.\n'+('Gửi tin liên tục hoặc bấm Xem tổng.' if cfg['ready'] else 'Chưa có %: bấm Sửa % trước.')

async def show_card(update,context):
    p=current(update,context)
    context.user_data['seen_profile']=p['id'];context.user_data['seen_config']=p['config']
    await reply(update,card(p)+'\nNgày chung: '+context.user_data.get('day',today()))

async def start(update,context):
    if not allowed(update):return
    clear_pending(context)
    shared_day(update,context)
    await reply(update,'Bot tính tiền khách/chủ theo ngày. Bấm Tạo người để thêm tên và đặt tỷ lệ. Chỉ nhận chữ.\nNgày: '+context.user_data['day'])

async def choose(update,context):
    ps=DB.profiles(workspace_owner(),actor=update.effective_user.id);context.user_data['state']='choose'
    await reply(update,'Bảng của ai? Gửi số ID hoặc đúng tên:\n'+'\n'.join(f"{p['id']}: {p['name']} — {p['side']}" for p in ps))

async def handle(update,context):
    if not allowed(update):
        clear_pending(context);return
    owner=workspace_owner();actor=update.effective_user.id;raw=update.effective_message.text.strip()
    try:
        day,changed=shared_day(update,context);state=context.user_data.get('state')
        if changed and raw in NAVIGATION:await reply(update,'Ngày chung vừa đổi thành '+day+'. Đã hủy thao tác chờ của bạn.')
        if changed and raw not in NAVIGATION:raise ValueError('Ngày chung đã đổi thành '+day+'. Đã hủy thao tác chờ; chưa lưu gì. Kiểm tra ngày rồi gửi lại.')
        if raw in USER_ACTIONS or state in ('add_users','remove_users','confirm_remove_users'):
            if not is_owner(update):raise ValueError('Chỉ OWNER được quản lý người sử dụng.')
        if raw in NAVIGATION:
            clear_pending(context)
            state=None
        if raw in ('👥 Người sử dụng','📋 Danh sách'):await show_users(update);return
        if raw=='↩️ Quay lại':await reply(update,'Đã về menu tính tiền.');return
        if raw=='➕ Thêm người':
            context.user_data['state']='add_users';await reply(update,'Gửi Telegram User ID cần thêm. Có thể dán nhiều ID, cách nhau bằng xuống dòng, dấu phẩy hoặc khoảng trắng.',USER_MENU);return
        if raw=='➖ Xóa người':
            context.user_data['state']='remove_users';await reply(update,'Gửi một hoặc nhiều Telegram User ID cần gỡ quyền. OWNER không thể bị gỡ.',USER_MENU);return
        if state=='add_users':
            added,existing=DB.add_users(owner,actor,raw);clear_pending(context)
            await reply(update,'✅ Thêm mới: '+str(len(added))+'\n'+'\n'.join(map(str,added))+'\nℹ️ Đã có sẵn: '+str(len(existing)),USER_MENU);return
        if state=='remove_users':
            ids=user_ids(raw)
            if owner in ids:raise ValueError('Không thể gỡ quyền OWNER. Chưa gỡ ai.')
            context.user_data['remove_users']=ids;context.user_data['state']='confirm_remove_users'
            await reply(update,'Sắp gỡ quyền:\n'+'\n'.join(map(str,ids))+'\n\nGửi XÓA QUYỀN để xác nhận, hoặc Hủy.',USER_MENU);return
        if state=='confirm_remove_users':
            if raw!='XÓA QUYỀN':raise ValueError('Gửi XÓA QUYỀN để xác nhận, hoặc Hủy. Chưa gỡ ai.')
            removed,missing=DB.remove_users(owner,actor,' '.join(map(str,context.user_data['remove_users'])),confirmed=True);clear_pending(context)
            await reply(update,'Đã gỡ quyền: '+str(len(removed))+'\n'+'\n'.join(map(str,removed))+'\nKhông có sẵn: '+str(len(missing)),USER_MENU);return
        if raw=='Hủy':context.user_data.pop('state',None);await reply(update,'Đã hủy.');return
        if raw in ('Nhập tin','Đổi người'):await choose(update,context);return
        if raw=='Tạo người':context.user_data['state']='create';await reply(update,'Gửi:\nKhách HBX\nhoặc:\nChủ OK\nTên có thể có khoảng trắng.');return
        if raw=='Đổi ngày':context.user_data['state']='day';await reply(update,'Gửi ngày dạng 06-10-2026.');return
        if raw=='Nợ cũ':
            p=current(update,context);context.user_data['state']='old_balance'
            await reply(update,f"Nợ cũ của {p['name']} (góc nhìn của mày).\nGửi:\nTHU 2356\nhoặc\nTRẢ 2356\nhoặc\n0\nSố mới thay số dư cũ; áp dụng cho người này khi xem tổng, không tự cộng dồn.");return
        if raw=='Xem raw':
            current(update,context);context.user_data['state']='raw'
            await reply(update,'Gửi ID cần xem raw trong sổ của người/ngày đang chọn.');return
        if raw in ('Sửa %','Sửa thưởng'):
            current(update,context);context.user_data['state']='percent' if raw=='Sửa %' else 'reward'
            await reply(update,'Chỉ đổi cho tin mới. Tin cũ giữ tỷ lệ lúc nhập.\n'+('Gửi 5 số theo thứ tự:\nĐề Bao Xiên 2 Xiên 3,4 Càng\nVí dụ:\n5 3,5 18 21 38\nSố lẻ dùng dấu phẩy, ví dụ 5,5.' if raw=='Sửa %' else 'Gửi 7 số theo thứ tự:\nĐề Bao Xiên 2 Xiên 3 Xiên 4 Càng Áp càng\nVí dụ:\n90 3,5 15 48 180 400 10\nSố lẻ dùng dấu phẩy, ví dụ 3,5.'));return
        if raw in ('Xiên ×14','Xiên ×15'):
            p=current(update,context);DB.select_variant(owner,p['id'],raw[-2:],actor=actor);await show_card(update,context);return
        if raw in ('Sửa tin','Xóa tin'):
            p=current(update,context);context.user_data['state']='replace' if raw=='Sửa tin' else 'delete'
            if raw=='Sửa tin':context.user_data['edit_revisions']={r['id']:r['revision'] for r in DB.tickets(owner,p['id'],day,actor=actor)}
            await reply(update,'Gửi ID; nội dung mới' if raw=='Sửa tin' else 'Gửi ID cần xóa; bot sẽ hỏi xác nhận.');return
        if raw in ('Danh sách tin','Sổ vé'):
            p=current(update,context);rows=DB.tickets(owner,p['id'],day,actor=actor)
            await reply(update,render_book(p,day,rows));return
        if raw=='Xem tổng':
            p=current(update,context);rows=DB.tickets(owner,p['id'],day,actor=actor);result=None
            if rows:
                try:
                    candidate=await asyncio.to_thread(fetch_latest_result,True)
                    if candidate.date==day:result=candidate
                except ResultError:pass
            await reply(update,render_summary(p,day,rows,result));return
        if state=='create':
            side,name=profile_input(raw);pid=DB.create(owner,side,name,actor=actor);context.user_data['profile']=pid
            context.user_data.pop('state',None);await show_card(update,context);return
        if state=='choose':
            ps=DB.profiles(owner,actor=actor);matches=[p for p in ps if str(p['id'])==raw or p['name'].casefold()==raw.casefold()]
            if len(matches)!=1:raise ValueError('Tên chưa có hoặc trùng. Gửi ID trong danh sách, hoặc bấm Tạo người.')
            context.user_data['profile']=matches[0]['id'];context.user_data.pop('state',None);await show_card(update,context);return
        if state=='day':
            new_day=datetime.strptime(raw,'%d-%m-%Y').strftime('%d-%m-%Y');DB.set_day(owner,actor,new_day)
            context.user_data['day']=new_day;clear_pending(context);await reply(update,'Ngày chung của mọi người: '+new_day);return
        p=current(update,context)
        if state=='old_balance':
            DB.set_old_balance(owner,p['id'],raw,actor=actor);clear_pending(context)
            await reply(update,'Đã lưu nợ cũ cho '+p['name']+'. Xem tổng sẽ gộp với tiền hiện tại.');return
        if state=='raw':
            rows=[r for r in DB.tickets(owner,p['id'],day,actor=actor) if r['id']==int(raw)]
            if not rows:raise ValueError('ID không thuộc bảng/ngày đang chọn hoặc đã xóa.')
            clear_pending(context);await reply(update,f"Raw ID {rows[0]['id']}:\n{rows[0]['raw']}");return
        if state=='b_choice':
            pending=context.user_data.get('pending_b')
            if (not pending or pending['expires']<time.time() or pending['profile']!=p['id']
                    or pending['day']!=day or pending['config']!=p['config']):
                clear_pending(context)
                raise ValueError('Lựa chọn hết hiệu lực hoặc bảng/tỷ lệ đã đổi. Gửi lại tin.')
            if raw not in ('BAO TOÀN BỘ','ĐỀ BỘ'):
                raise ValueError('Chọn BAO TOÀN BỘ, ĐỀ BỘ hoặc Hủy. Chưa lưu tin.')
            corrected=pending['bao' if raw=='BAO TOÀN BỘ' else 'bo']
            await save_input(update,context,p,day,corrected,pending['message'],pending['tid'])
            return
        if state in ('percent','reward'):
            DB.configure(owner,p['id'],state,percent_input(raw) if state=='percent' else reward_input(raw),actor=actor);context.user_data.pop('state',None);await show_card(update,context);return
        if state=='replace':
            tid,body=raw.split(';',1)
            if int(tid) not in context.user_data.get('edit_revisions',{}):
                raise ValueError('ID không thuộc bảng/ngày đang chọn.')
            await save_input(update,context,p,day,body.strip(),update.effective_message.message_id,int(tid));return
        if state=='delete':
            tid=int(raw)
            row=next((r for r in DB.tickets(owner,p['id'],day,actor=actor) if r['id']==tid),None)
            if row is None:raise ValueError('Vé đã thay đổi/xóa hoặc không thuộc bảng/ngày này. Mở lại Xóa tin.')
            context.user_data['delete_revision']=row['revision']
            context.user_data['delete_id']=tid;context.user_data['delete_context']=(p['id'],day);context.user_data['state']='confirm_delete';await reply(update,f'Gửi XÓA để xóa ID {tid}, hoặc Hủy.');return
        if state=='confirm_delete':
            if raw!='XÓA':raise ValueError('Gửi XÓA hoặc Hủy.')
            if context.user_data.get('delete_context')!=(p['id'],day):
                clear_pending(context);raise ValueError('Bảng/ngày đã đổi. Chọn lại Xóa tin.')
            DB.delete(owner,p['id'],day,context.user_data['delete_id'],actor=actor,expected_revision=context.user_data.get('delete_revision'));clear_pending(context);await reply(update,'Đã xóa tin khỏi tổng.');return
        await save_input(update,context,p,day,raw,update.effective_message.message_id)
    except ValueError as exc:await reply(update,str(exc))
    except ArithmeticError:await reply(update,'Không tính/chốt tiền: vượt độ chính xác số hỗ trợ. Kiểm tra dữ liệu.')
    except Exception:
        logging.exception('Xử lý thất bại');await reply(update,'Có lỗi. Chưa xác nhận thao tác; kiểm tra Sổ vé trước khi gửi lại.')

async def startup_notice(application):
    print('================================\nBOT ĐANG CHẠY\nKhông đóng cửa sổ này.\nMở Telegram để sử dụng bot.\n================================')

def main():
    from local_config import validate_token, validate_admin, install_redaction
    token=validate_token(os.getenv('TELEGRAM_BOT_TOKEN',''));validate_admin(os.getenv('TELEGRAM_ADMIN_ID',''))
    install_redaction(token)
    app=Application.builder().token(token).post_init(startup_notice).build();app.add_handler(CommandHandler('start',start))
    app.add_handler(CommandHandler('tong',handle_command_total))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,handle));app.run_polling()
async def handle_command_total(update,context):
    if not allowed(update):return
    try:
        clear_pending(context)
        p=current(update,context);day,_=shared_day(update,context);result=None
        try:
            candidate=await asyncio.to_thread(fetch_latest_result,True)
            if candidate.date==day:result=candidate
        except ResultError:pass
        await reply(update,render_summary(p,day,DB.tickets(workspace_owner(),p['id'],day,actor=update.effective_user.id),result))
    except ValueError as exc:await reply(update,str(exc))
    except ArithmeticError:await reply(update,'Không chốt tiền: vượt độ chính xác số hỗ trợ.')
    except Exception:
        logging.exception('Không tính được tổng');await reply(update,'Không chốt tiền: dữ liệu hoặc kết quả có lỗi.')
if __name__=='__main__':main()
