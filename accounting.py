"""Daily accounting. All stored money uses thousands of VND (k)."""
import json
import re
import sqlite3
from contextlib import closing
from decimal import Decimal, ROUND_HALF_UP
from calculator import calculate, RATES, format_amount
from results import _winning_for_entry

KINDS = ('Đề', 'Bao', 'Xiên 2', 'Xiên 3', 'Xiên 4', 'Càng', 'Áp càng')
DEFAULT_REWARDS = {**{k: str(v) for k, v in RATES.items()}, 'Áp càng': '10'}

def number(value):
    d = Decimal(str(value).replace(',', '.'))
    if not d.is_finite():
        raise ValueError('Số phải hữu hạn.')
    return d

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
        p=self.profile(owner,pid);cfg=p['config']
        if cfg['ready']:cfg.setdefault('variants',{})[cfg.get('active','15')]=cfg['percent'].copy()
        cfg['active']=variant;cfg['reward']['Xiên 2']=variant
        cfg['percent']=cfg['variants'].get(variant,{k:'0' for k in KINDS}).copy()
        cfg['ready']=variant in cfg['variants']
        self.query('UPDATE profiles SET config=? WHERE owner=? AND id=?',(json.dumps(cfg,ensure_ascii=False),owner,pid),True)
    def add(self, owner, pid, day, message, raw):
        p=self.profile(owner,pid)
        if not p['config']['ready']:raise ValueError('Hãy lưu % trước khi nhập tin (có thể nhập toàn số 0).')
        parsed=calculate(raw)
        if parsed.rejected or not parsed.entries:
            raise ValueError('Chưa lưu tin. Phần chưa hiểu: '+ '; '.join(parsed.rejected))
        existing=self.query('SELECT id FROM tickets WHERE owner=? AND message=?',(owner,message))
        if existing:return False
        self.query('INSERT INTO tickets(owner,profile,day,message,raw,config) VALUES(?,?,?,?,?,?)',
                   (owner,pid,day,message,raw,json.dumps(p['config'],ensure_ascii=False)),True)
        return True
    def tickets(self,owner,pid,day):
        return self.query('SELECT * FROM tickets WHERE owner=? AND profile=? AND day=? ORDER BY id',(owner,pid,day))
    def delete(self,owner,pid,day,tid):
        self.query('DELETE FROM tickets WHERE owner=? AND profile=? AND day=? AND id=?',(owner,pid,day,tid),True)
    def replace(self,owner,pid,day,tid,raw):
        if not any(r['id']==tid for r in self.tickets(owner,pid,day)):raise ValueError('ID không thuộc bảng/ngày đang chọn.')
        parsed=calculate(raw)
        if parsed.rejected or not parsed.entries:raise ValueError('Tin sửa chưa được hiểu đủ; giữ nguyên tin cũ.')
        self.query('UPDATE tickets SET raw=? WHERE owner=? AND profile=? AND day=? AND id=?',(raw,owner,pid,day,tid),True)

def totals(rows, result=None):
    out={k:[Decimal(0),Decimal(0),Decimal(0)] for k in KINDS}
    for row in rows:
        cfg=json.loads(row['config'])
        for e in calculate(row['raw']).entries:
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

def summary(profile, day, rows, result=None):
    if result and result.date!=day:raise ValueError('Kết quả không đúng ngày; không tính thưởng.')
    parts=totals(rows,result);lines=[f"{profile['side']} {profile['name']} — {day}",f'{len(rows)} tin']
    for k,(goods,cut,reward) in parts.items():
        if goods or reward:lines.append(f'{k}: hàng {format_amount(goods)}; trừ % {format_amount(cut)}; thưởng '+(format_amount(reward) if result else 'chưa có'))
    goods=sum(t[0] for t in parts.values());cut=sum(t[1] for t in parts.values())
    lines.append(f'Tổng hàng: {format_amount(goods)} | Trừ %: {format_amount(cut)}')
    if result is None:return '\n'.join(lines+['Chưa có kết quả đúng ngày. Chưa chốt tiền thu/trả.'])
    reward=sum(t[2] for t in parts.values());balance=goods-cut-reward
    receive=balance>0 if profile['side']=='Khách' else balance<0
    amount=abs(balance).quantize(Decimal('1'),rounding=ROUND_HALF_UP)
    lines.append(f'Tổng thưởng: {format_amount(reward)}')
    lines.append('Cân bằng: không thu/trả.' if balance==0 else f"Mày {'thu' if receive else 'trả'} {profile['name']}: {format_amount(amount)} (đã làm tròn)")
    return '\n'.join(lines)
