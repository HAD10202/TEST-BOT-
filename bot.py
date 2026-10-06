"""Small Telegram UI; calculator remains unchanged."""
import asyncio
import logging
import os
from datetime import datetime
from zoneinfo import ZoneInfo
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from accounting import Ledger, summary
from results import fetch_latest_result, ResultError

logging.basicConfig(level=logging.WARNING)
logging.getLogger('httpx').setLevel(logging.WARNING)
MENU=ReplyKeyboardMarkup([['Nhập tin','Xem tổng'],['Đổi người','Danh sách tin'],['Tạo người','Sửa %','Sửa thưởng'],['Xiên ×14','Xiên ×15'],['Đổi ngày','Sửa tin','Xóa tin'],['Hủy']],resize_keyboard=True,is_persistent=True)
DB=Ledger(os.getenv('BOT_DB','data.sqlite3'))

def allowed(update):
    return update.effective_chat.type=='private' and str(update.effective_user.id)==os.getenv('TELEGRAM_ADMIN_ID','')

def today():return datetime.now(ZoneInfo('Asia/Ho_Chi_Minh')).strftime('%d-%m-%Y')
async def reply(update,text):
    for start in range(0,len(text),3500):await update.effective_message.reply_text(text[start:start+3500],reply_markup=MENU)

def current(update,context):
    pid=context.user_data.get('profile')
    if not pid:raise ValueError('Bấm Nhập tin rồi chọn tên trước.')
    return DB.profile(update.effective_user.id,pid)

def card(p):
    cfg=p['config'];v=cfg.get('active','15');pc=cfg.get('variants',{}).get(v,cfg['percent'])
    return f"{p['name']} — {p['side']}\n"+'\n'.join(f'{k}: {pc[k]}% — thưởng ×'+(v if k=='Xiên 2' else cfg['reward'][k]) for k in ('Đề','Bao','Xiên 2','Xiên 3','Xiên 4','Càng'))+'\n% đang sửa thuộc bộ Xiên ×'+v+'; chỉ áp dụng cho tin mới.\n'+('Gửi tin liên tục hoặc bấm Xem tổng.' if cfg['ready'] else 'Chưa có %: bấm Sửa % trước.')

async def start(update,context):
    if not allowed(update):return
    context.user_data.setdefault('day',today())
    await reply(update,'Bot tính tiền khách/chủ theo ngày. Bấm Tạo người để thêm tên và đặt tỷ lệ. Chỉ nhận chữ.\nNgày: '+context.user_data['day'])

async def choose(update,context):
    ps=DB.profiles(update.effective_user.id);context.user_data['state']='choose'
    await reply(update,'Bảng của ai? Gửi số ID hoặc đúng tên:\n'+'\n'.join(f"{p['id']}: {p['name']} — {p['side']}" for p in ps))

async def handle(update,context):
    if not allowed(update):return
    owner=update.effective_user.id;raw=update.effective_message.text.strip();state=context.user_data.get('state');day=context.user_data.setdefault('day',today())
    try:
        if raw=='Hủy':context.user_data.pop('state',None);await reply(update,'Đã hủy.');return
        if raw in ('Nhập tin','Đổi người'):await choose(update,context);return
        if raw=='Tạo người':context.user_data['state']='create';await reply(update,'Gửi: Khách; HBX hoặc Chủ; Tên chủ');return
        if raw=='Đổi ngày':context.user_data['state']='day';await reply(update,'Gửi ngày dạng 06-10-2026.');return
        if raw in ('Sửa %','Sửa thưởng'):
            current(update,context);context.user_data['state']='percent' if raw=='Sửa %' else 'reward'
            await reply(update,'Chỉ đổi cho tin mới. Tin cũ giữ tỷ lệ lúc nhập.\n'+('Gửi 5 % theo Đề; Bao; Xiên 2; Xiên 3,4; Càng\nVí dụ: 5; 3,5; 18; 23; 38' if raw=='Sửa %' else 'Gửi 7 hệ số: Đề; Bao; Xiên 2; Xiên 3; Xiên 4; Càng; Áp càng\nVí dụ: 90; 3,5; 14; 48; 180; 400; 10'));return
        if raw in ('Xiên ×14','Xiên ×15'):
            p=current(update,context);DB.select_variant(owner,p['id'],raw[-2:]);await reply(update,card(current(update,context)));return
        if raw in ('Sửa tin','Xóa tin'):
            current(update,context);context.user_data['state']='replace' if raw=='Sửa tin' else 'delete'
            await reply(update,'Gửi ID; nội dung mới' if raw=='Sửa tin' else 'Gửi ID cần xóa; bot sẽ hỏi xác nhận.');return
        if raw=='Danh sách tin':
            p=current(update,context);rows=DB.tickets(owner,p['id'],day)
            await reply(update,'\n'.join(f"ID {r['id']}: {r['raw']}" for r in rows) or 'Chưa có tin.');return
        if raw=='Xem tổng':
            p=current(update,context);rows=DB.tickets(owner,p['id'],day);result=None
            if rows:
                try:
                    candidate=await asyncio.to_thread(fetch_latest_result,True)
                    if candidate.date==day:result=candidate
                except ResultError:pass
            await reply(update,summary(p,day,rows,result));return
        if state=='create':
            side,name=raw.split(';',1);pid=DB.create(owner,side.strip(),name.strip());context.user_data['profile']=pid
            context.user_data.pop('state',None);await reply(update,card(current(update,context)));return
        if state=='choose':
            ps=DB.profiles(owner);matches=[p for p in ps if str(p['id'])==raw or p['name'].casefold()==raw.casefold()]
            if len(matches)!=1:raise ValueError('Tên chưa có hoặc trùng. Gửi ID trong danh sách, hoặc bấm Tạo người.')
            context.user_data['profile']=matches[0]['id'];context.user_data.pop('state',None);await reply(update,card(current(update,context)));return
        if state=='day':
            context.user_data['day']=datetime.strptime(raw,'%d-%m-%Y').strftime('%d-%m-%Y');context.user_data.pop('state',None);await reply(update,'Ngày: '+context.user_data['day']);return
        p=current(update,context)
        if state in ('percent','reward'):
            DB.configure(owner,p['id'],state,raw);context.user_data.pop('state',None);await reply(update,card(current(update,context)));return
        if state=='replace':
            tid,body=raw.split(';',1);DB.replace(owner,p['id'],day,int(tid),body.strip());context.user_data.pop('state',None);await reply(update,'Đã sửa tin; tổng sẽ tính lại.');return
        if state=='delete':
            tid=int(raw)
            if not any(r['id']==tid for r in DB.tickets(owner,p['id'],day)):raise ValueError('ID không thuộc bảng/ngày đang chọn.')
            context.user_data['delete_id']=tid;context.user_data['state']='confirm_delete';await reply(update,f'Gửi XÓA để xóa ID {tid}, hoặc Hủy.');return
        if state=='confirm_delete':
            if raw!='XÓA':raise ValueError('Gửi XÓA hoặc Hủy.')
            DB.delete(owner,p['id'],day,context.user_data.pop('delete_id'));context.user_data.pop('state',None);await reply(update,'Đã xóa tin khỏi tổng.');return
        fresh=DB.add(owner,p['id'],day,update.effective_message.message_id,raw)
        rows=DB.tickets(owner,p['id'],day)
        await reply(update,('Đã lưu' if fresh else 'Tin đã có, không ghi lại')+f" — {p['name']} — {day}\nSố tin: {len(rows)}\nID: {rows[-1]['id']}\nBấm Xem tổng để tính thưởng và thu/trả.")
    except (ValueError, ArithmeticError) as exc:await reply(update,str(exc))
    except Exception:
        logging.exception('Xử lý thất bại');await reply(update,'Có lỗi. Chưa xác nhận thao tác; kiểm tra Danh sách tin trước khi gửi lại.')

def main():
    token=os.getenv('TELEGRAM_BOT_TOKEN','').strip();admin=os.getenv('TELEGRAM_ADMIN_ID','').strip()
    if not token or not admin.isdigit():raise RuntimeError('Thiếu token hoặc admin ID số.')
    app=Application.builder().token(token).build();app.add_handler(CommandHandler('start',start))
    app.add_handler(CommandHandler('tong',handle_command_total))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,handle));app.run_polling()
async def handle_command_total(update,context):
    if not allowed(update):return
    p=current(update,context);day=context.user_data.setdefault('day',today());result=None
    try:
        candidate=await asyncio.to_thread(fetch_latest_result,True)
        if candidate.date==day:result=candidate
    except ResultError:pass
    await reply(update,summary(p,day,DB.tickets(update.effective_user.id,p['id'],day),result))
if __name__=='__main__':main()
