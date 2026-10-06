"""Daily accounting. All stored money uses thousands of VND (k)."""
import json
import re
import sqlite3
from contextlib import closing
from decimal import Decimal, ROUND_HALF_UP, Inexact, localcontext
from datetime import datetime, timezone
from dataclasses import asdict
from calculator import calculate, RATES, format_amount, Entry, propose_b_choice, format_check, exact_decimal
from results import _winning_for_entry

KINDS = ('Đề', 'Bao', 'Xiên 2', 'Xiên 3', 'Xiên 4', 'Càng', 'Áp càng')
DEFAULT_REWARDS = {**{k: str(v) for k, v in RATES.items()}, 'Áp càng': '10'}

def number(value):
    if (not re.fullmatch(r'[+-]?\d+(?:[.,]\d+)?(?:[eE][+-]?\d{1,2})?', str(value))
            or len(str(value)) > 80):
        raise ValueError('Số không hợp lệ hoặc vượt độ chính xác hỗ trợ.')
    d = Decimal(str(value).replace(',', '.'))
    if not d.is_finite():
        raise ValueError('Số phải hữu hạn.')
    if d.adjusted() > 70 or d.as_tuple().exponent < -70:
        raise ValueError('Số vượt độ chính xác hỗ trợ.')
    return d

def checked_calculation(raw):
    if propose_b_choice(raw):
        raise ValueError('B chưa rõ: chọn BAO TOÀN BỘ hoặc ĐỀ BỘ trước khi lưu.')
    parsed = calculate(raw)
    if parsed.rejected or not parsed.entries:
        raise ValueError('CHƯA LƯU TOÀN BỘ TIN.\nĐã hiểu / Chưa hiểu:\n' + format_check(parsed))
    stored_entries({'entries_snapshot': snapshot(parsed), 'id': 'mới'})
    return parsed

def snapshot(parsed):
    return json.dumps({'version': 1, 'entries': [
        {**asdict(e), 'unit_stake': str(e.unit_stake)} for e in parsed.entries
    ]}, ensure_ascii=False)

def stored_entries(row):
    if not row.get('entries_snapshot'):
        raise ValueError(f"Vé cũ ID {row.get('id')}: chưa có bản lưu cách hiểu. Kiểm tra và Sửa tin để xác nhận; chưa chốt tổng.")
    try:
        data = json.loads(row['entries_snapshot'])
        if data['version'] != 1 or not data['entries']:
            raise ValueError('Sai phiên bản vé')
        entries = []
        for item in data['entries']:
            e = Entry(item['kind'], tuple(item['numbers']), number(item['unit_stake']),
                      item['ticket_count'], item['source'], tuple(tuple(g) for g in item['ticket_groups']))
            if (e.kind not in RATES or e.unit_stake <= 0
                    or type(e.ticket_count) is not int or e.ticket_count <= 0
                    or any(not re.fullmatch(r'\d{3}' if e.kind == 'Càng' else r'\d{2}', n) for n in e.numbers)):
                raise ValueError('Vé không hợp lệ')
            if e.kind.startswith('Xiên'):
                level = int(e.kind[-1])
                if (not e.ticket_groups or e.ticket_count != len(e.ticket_groups)
                        or any(len(g) != level or len(set(g)) != level or any(n not in e.numbers for n in g) for g in e.ticket_groups)):
                    raise ValueError('Nhóm Xiên không hợp lệ')
            elif e.ticket_count != len(e.numbers) or e.ticket_groups:
                raise ValueError('Số vé không khớp')
            entries.append(e)
        return entries
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"Bản lưu vé ID {row.get('id')} hỏng; chưa tính tổng.") from exc

def validate_result(result, day):
    if result.date != day:
        raise ValueError('Kết quả không đúng ngày; không tính thưởng.')
    if (not re.fullmatch(r'\d{5}', result.special_full) or len(result.loto) != 27
            or any(not re.fullmatch(r'\d{2}', n) for n in result.loto)
            or result.de_number not in result.loto):
        raise ValueError('Kết quả không đủ hoặc không hợp lệ; chưa tính thưởng.')

def validate_config(cfg):
    try:
        for kind in KINDS:
            if not 0 <= number(cfg['percent'][kind]) <= 100 or number(cfg['reward'][kind]) <= 0:
                raise ValueError('Tỷ lệ không hợp lệ')
        if number(cfg['reward']['Xiên 2']) not in (Decimal(14), Decimal(15)):
            raise ValueError('Sai bộ Xiên')
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError('Bản lưu tỷ lệ hỏng hoặc không hợp lệ; chưa tính tiền.') from exc

class Ledger:
    def __init__(self, path='data.sqlite3'):
        self.path = str(path)
        with closing(sqlite3.connect(self.path)) as c:
            c.executescript('''
            CREATE TABLE IF NOT EXISTS profiles(id INTEGER PRIMARY KEY, owner INTEGER NOT NULL,
              side TEXT NOT NULL, name TEXT NOT NULL, config TEXT NOT NULL,
              UNIQUE(owner,side,name));
            CREATE TABLE IF NOT EXISTS tickets(id INTEGER PRIMARY KEY, owner INTEGER NOT NULL,
              profile INTEGER NOT NULL, day TEXT NOT NULL, message INTEGER NOT NULL,
              raw TEXT NOT NULL, config TEXT NOT NULL, UNIQUE(owner,message));
            ''')
            columns = {r[1] for r in c.execute('PRAGMA table_info(tickets)')}
            if 'entries_snapshot' not in columns:
                c.execute('ALTER TABLE tickets ADD COLUMN entries_snapshot TEXT')
            if 'deleted_at' not in columns:
                c.execute('ALTER TABLE tickets ADD COLUMN deleted_at TEXT')
            c.execute('''CREATE TABLE IF NOT EXISTS ticket_audit(
                id INTEGER PRIMARY KEY, ticket INTEGER NOT NULL, actor INTEGER NOT NULL,
                action TEXT NOT NULL, at TEXT NOT NULL, old_raw TEXT, new_raw TEXT)''')
            c.commit()
    def query(self, sql, args=(), write=False):
        with closing(sqlite3.connect(self.path)) as c:
            c.row_factory = sqlite3.Row
            cur = c.execute(sql, args)
            if write:
                c.commit()
                return cur.lastrowid
            return [dict(x) for x in cur.fetchall()]
    def profiles(self, owner):
        return self.query('SELECT * FROM profiles WHERE owner=? ORDER BY side,name', (owner,))
    def profile(self, owner, pid):
        rows = self.query('SELECT * FROM profiles WHERE owner=? AND id=?', (owner,pid))
        if not rows: raise ValueError('Không tìm thấy người này.')
        p=rows[0];p['config']=json.loads(p['config']);return p
    def create(self, owner, side, name):
        if side not in ('Khách','Chủ') or not name.strip() or len(name)>80:
            raise ValueError('Chọn Khách/Chủ và tên dài tối đa 80 ký tự.')
        cfg={'percent': {k:'0' for k in KINDS},'reward':DEFAULT_REWARDS.copy(),'ready':False}
        return self.query('INSERT INTO profiles(owner,side,name,config) VALUES(?,?,?,?)',
                          (owner,side,name.strip(),json.dumps(cfg,ensure_ascii=False)),True)
    def configure(self, owner, pid, field, text):
        if field not in ('percent', 'reward'):raise ValueError('Trường cấu hình không hợp lệ.')
        p=self.profile(owner,pid);cfg=p['config']
        vals=[number(x.strip()) for x in re.split(r';|\s+-\s+',text)]
        count=5 if field=='percent' else 7
        if len(vals)!=count or any(x<0 or (field=='percent' and x>100) or (field=='reward' and x<=0) for x in vals):
            raise ValueError('Sai số lượng hoặc giá trị. % từ 0 đến 100; hệ số thưởng lớn hơn 0.')
        if field=='percent':
            d,b,x,y,z=map(str,vals)
            cfg['percent']=dict(zip(KINDS,(d,b,x,y,y,z,'0')));cfg['ready']=True
        else:
            cfg['reward']=dict(zip(KINDS,map(str,vals)))
            if cfg['reward']['Xiên 2'] not in ('14','15'):raise ValueError('Xiên 2 chọn 14 hoặc 15.')
            variant=cfg['reward']['Xiên 2']
            old=cfg.get('active','15')
            if variant!=old:
                if cfg['ready']:cfg.setdefault('variants',{})[old]=cfg['percent'].copy()
                cfg['percent']=cfg.get('variants',{}).get(variant,{k:'0' for k in KINDS}).copy()
                cfg['ready']=variant in cfg.get('variants',{})
                cfg['active']=variant
        if cfg['ready']:cfg.setdefault('variants',{})[cfg.get('active','15')]=cfg['percent'].copy()
        self.query('UPDATE profiles SET config=? WHERE owner=? AND id=?',
                   (json.dumps(cfg,ensure_ascii=False),owner,pid),True)
    def select_variant(self,owner,pid,variant):
        if variant not in ('14', '15'):raise ValueError('Chỉ chọn Xiên ×14 hoặc ×15.')
        p=self.profile(owner,pid);cfg=p['config']
        cfg.setdefault('variants', {})
        if cfg['ready']:cfg.setdefault('variants',{})[cfg.get('active','15')]=cfg['percent'].copy()
        cfg['active']=variant;cfg['reward']['Xiên 2']=variant
        cfg['percent']=cfg['variants'].get(variant,{k:'0' for k in KINDS}).copy()
        cfg['ready']=variant in cfg['variants']
        self.query('UPDATE profiles SET config=? WHERE owner=? AND id=?',(json.dumps(cfg,ensure_ascii=False),owner,pid),True)
    def add(self, owner, pid, day, message, raw):
        if datetime.strptime(day, '%d-%m-%Y').strftime('%d-%m-%Y') != day:
            raise ValueError('Ngày không hợp lệ.')
        p=self.profile(owner,pid)
        if not p['config']['ready']:raise ValueError('Hãy lưu % trước khi nhập tin (có thể nhập toàn số 0).')
        validate_config(p['config'])
        parsed=checked_calculation(raw)
        with closing(sqlite3.connect(self.path)) as c:
            with c:
                cur = c.execute('INSERT INTO tickets(owner,profile,day,message,raw,config,entries_snapshot) VALUES(?,?,?,?,?,?,?) ON CONFLICT(owner,message) DO NOTHING',
                                (owner,pid,day,message,raw,json.dumps(p['config'],ensure_ascii=False),snapshot(parsed)))
                return cur.rowcount == 1
    def tickets(self,owner,pid,day):
        return self.query('SELECT * FROM tickets WHERE owner=? AND profile=? AND day=? AND deleted_at IS NULL ORDER BY id',(owner,pid,day))
    def delete(self,owner,pid,day,tid):
        self._mutate(owner, pid, day, tid, None)
    def replace(self,owner,pid,day,tid,raw):
        self._mutate(owner, pid, day, tid, raw)
    def _mutate(self, owner, pid, day, tid, raw):
        parsed = checked_calculation(raw) if raw is not None else None
        at = datetime.now(timezone.utc).isoformat()
        with closing(sqlite3.connect(self.path)) as c:
            with c:
                c.execute('BEGIN IMMEDIATE')
                row = c.execute('SELECT raw FROM tickets WHERE owner=? AND profile=? AND day=? AND id=? AND deleted_at IS NULL', (owner,pid,day,tid)).fetchone()
                if not row:raise ValueError('ID không thuộc bảng/ngày đang chọn hoặc đã xóa.')
                if raw is None:
                    c.execute('UPDATE tickets SET deleted_at=? WHERE id=?', (at,tid))
                else:
                    c.execute('UPDATE tickets SET raw=?,entries_snapshot=? WHERE id=?', (raw,snapshot(parsed),tid))
                c.execute('INSERT INTO ticket_audit(ticket,actor,action,at,old_raw,new_raw) VALUES(?,?,?,?,?,?)',
                          (tid,owner,'delete' if raw is None else 'edit',at,row[0],raw))

@exact_decimal
def totals(rows, result=None):
    out={k:[Decimal(0),Decimal(0),Decimal(0)] for k in KINDS}
    for row in rows:
        if row.get('deleted_at'):continue
        if result:validate_result(result, row['day'])
        cfg=json.loads(row['config'])
        validate_config(cfg)
        for e in stored_entries(row):
            key=e.kind+' ×'+cfg['reward']['Xiên 2'] if e.kind=='Xiên 2' else e.kind
            t=out.setdefault(key,[Decimal(0),Decimal(0),Decimal(0)]);t[0]+=e.stake;t[1]+=e.stake*number(cfg['percent'][e.kind])/100
            if result is None:continue
            if e.kind=='Càng':
                exact=sum(n==result.cang_number for n in e.numbers)
                ap=sum(n!=result.cang_number and n[-2:]==result.de_number for n in e.numbers)
                t[2]+=e.unit_stake*exact*number(cfg['reward']['Càng'])
                out['Áp càng'][2]+=e.unit_stake*ap*number(cfg['reward']['Áp càng'])
            else:
                base,_,_,_=_winning_for_entry(e,result)
                t[2]+=base*number(cfg['reward'][e.kind])
    return out

@exact_decimal
def summary(profile, day, rows, result=None):
    if result:validate_result(result, day)
    if any(r['day'] != day or r['profile'] != profile['id'] or r['owner'] != profile['owner'] for r in rows):
        raise ValueError('Dữ liệu vé không thuộc bảng/ngày đang chọn.')
    parts=totals(rows,result);lines=[f"{profile['side']} {profile['name']} — {day}",f'{len(rows)} tin']
    for k,(goods,cut,reward) in parts.items():
        if goods or reward:lines.append(f'{k}: hàng {format_amount(goods)}; trừ % {format_amount(cut)}; thưởng '+(format_amount(reward) if result else 'chưa có'))
    goods=sum(t[0] for t in parts.values());cut=sum(t[1] for t in parts.values())
    lines.append(f'Tổng hàng: {format_amount(goods)} | Trừ %: {format_amount(cut)}')
    if result is None:return '\n'.join(lines+['Chưa có kết quả đúng ngày. Chưa chốt tiền thu/trả.'])
    reward=sum(t[2] for t in parts.values());balance=goods-cut-reward
    receive=balance>0 if profile['side']=='Khách' else balance<0
    with localcontext() as ctx:
        # The sole intentionally inexact operation: final round to 1k.
        ctx.traps[Inexact] = False
        amount=abs(balance).quantize(Decimal('1'),rounding=ROUND_HALF_UP)
    lines.append(f'Tổng thưởng: {format_amount(reward)}')
    lines.append('Cân bằng: không thu/trả.' if balance==0 else f"Mày {'thu' if receive else 'trả'} {profile['name']}: {format_amount(amount)} (đã làm tròn)")
    return '\n'.join(lines)
