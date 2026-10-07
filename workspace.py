"""Shared workspace authorization/storage. Original money functions stay intact."""
import json
import re
import sqlite3
from contextlib import closing, contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from decimal import Decimal
from accounting import Ledger, checked_calculation, snapshot, number, validate_config

MAX_ID=2**63-1

def telegram_id(value):
    raw=str(value)
    if not re.fullmatch(r'[0-9]+',raw) or not 0<int(raw)<=MAX_ID:
        raise ValueError('Telegram User ID phải là số nguyên dương hợp lệ.')
    return int(raw)

def user_ids(text):
    tokens=re.split(r'[, \t\r\n]+',text.strip())
    valid=[];invalid=[]
    for token in tokens:
        try:
            uid=telegram_id(token)
            if uid not in valid:valid.append(uid)
        except ValueError:invalid.append(token or '(trống)')
    if invalid:
        raise ValueError('Hợp lệ:\n'+('\n'.join(map(str,valid)) or '(không có)')+
                         '\n\nKhông hợp lệ:\n'+'\n'.join(invalid)+'\n\nChưa lưu gì. Gửi lại toàn bộ danh sách hợp lệ.')
    return valid

class WorkspaceLedger(Ledger):
    def __init__(self,path='data.sqlite3'):
        self._connection=ContextVar('workspace_connection_'+str(id(self)),default=None)
        super().__init__(path)
        with closing(sqlite3.connect(self.path)) as c:
            with c:
                c.executescript('''
                CREATE TABLE IF NOT EXISTS authorized_users(
                    workspace_owner INTEGER NOT NULL,user_id INTEGER NOT NULL,
                    added_by INTEGER NOT NULL,added_at TEXT NOT NULL,
                    PRIMARY KEY(workspace_owner,user_id));
                CREATE TABLE IF NOT EXISTS workspace_state(
                    workspace_owner INTEGER PRIMARY KEY,day TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS workspace_audit(
                    id INTEGER PRIMARY KEY,workspace_owner INTEGER NOT NULL,actor INTEGER NOT NULL,
                    action TEXT NOT NULL,at TEXT NOT NULL,target TEXT,old_value TEXT,new_value TEXT);
                CREATE TABLE IF NOT EXISTS telegram_messages(
                    workspace_owner INTEGER NOT NULL,actor INTEGER NOT NULL,message INTEGER NOT NULL,
                    ticket INTEGER NOT NULL,PRIMARY KEY(workspace_owner,actor,message));
                ''')
                cols={r[1] for r in c.execute('PRAGMA table_info(tickets)')}
                if 'revision' not in cols:c.execute('ALTER TABLE tickets ADD COLUMN revision INTEGER NOT NULL DEFAULT 0')

    def query(self,sql,args=(),write=False):
        bound=self._connection.get()
        if bound:
            cur=bound[0].execute(sql,args)
            return cur.lastrowid if write else [dict(r) for r in cur.fetchall()]
        return super().query(sql,args,write)

    def authorized(self,owner,actor):
        owner,actor=telegram_id(owner),telegram_id(actor)
        return owner==actor or bool(self.query('SELECT 1 FROM authorized_users WHERE workspace_owner=? AND user_id=?',(owner,actor)))

    def _actor(self,owner,actor):
        bound=self._connection.get()
        return telegram_id(actor if actor is not None else bound[2] if bound and bound[1]==owner else owner)

    def _require(self,owner,actor):
        if not self.authorized(owner,actor):raise ValueError('Bạn chưa được OWNER cấp quyền hoặc quyền đã bị gỡ.')

    @contextmanager
    def _write(self,owner,actor=None):
        owner=telegram_id(owner);actor=self._actor(owner,actor)
        with closing(sqlite3.connect(self.path)) as c:
            c.row_factory=sqlite3.Row
            with c:
                c.execute('BEGIN IMMEDIATE')
                token=self._connection.set((c,owner,actor))
                try:
                    self._require(owner,actor)
                    yield c,actor
                finally:self._connection.reset(token)

    def _audit(self,c,owner,actor,action,target=None,old=None,new=None):
        c.execute('INSERT INTO workspace_audit(workspace_owner,actor,action,at,target,old_value,new_value) VALUES(?,?,?,?,?,?,?)',
                  (owner,actor,action,datetime.now(timezone.utc).isoformat(),str(target) if target is not None else None,old,new))

    def users(self,owner,actor):
        if telegram_id(actor)!=telegram_id(owner):raise ValueError('Chỉ OWNER được quản lý người sử dụng.')
        return [r['user_id'] for r in self.query('SELECT user_id FROM authorized_users WHERE workspace_owner=? ORDER BY user_id',(owner,))]

    def add_users(self,owner,actor,text):
        ids=user_ids(text)
        with self._write(owner,actor) as (c,actor):
            if actor!=owner:raise ValueError('Chỉ OWNER được quản lý người sử dụng.')
            added=[];existing=[]
            for uid in ids:
                if uid==owner or c.execute('SELECT 1 FROM authorized_users WHERE workspace_owner=? AND user_id=?',(owner,uid)).fetchone():
                    existing.append(uid);continue
                c.execute('INSERT INTO authorized_users VALUES(?,?,?,?)',(owner,uid,actor,datetime.now(timezone.utc).isoformat()))
                self._audit(c,owner,actor,'grant',uid,new=str(uid));added.append(uid)
            return added,existing

    def remove_users(self,owner,actor,text,*,confirmed=False):
        ids=user_ids(text)
        if owner in ids:raise ValueError('Không thể gỡ quyền OWNER. Chưa gỡ ai.')
        if not confirmed:raise ValueError('Chưa xác nhận XÓA QUYỀN; chưa gỡ ai.')
        with self._write(owner,actor) as (c,actor):
            if actor!=owner:raise ValueError('Chỉ OWNER được quản lý người sử dụng.')
            removed=[];missing=[]
            for uid in ids:
                cur=c.execute('DELETE FROM authorized_users WHERE workspace_owner=? AND user_id=?',(owner,uid))
                if cur.rowcount:self._audit(c,owner,actor,'revoke',uid,old=str(uid));removed.append(uid)
                else:missing.append(uid)
            return removed,missing

    def profiles(self,owner,*,actor=None):
        self._require(owner,self._actor(owner,actor));return super().profiles(owner)
    def profile(self,owner,pid,*,actor=None):
        self._require(owner,self._actor(owner,actor));return super().profile(owner,pid)
    def tickets(self,owner,pid,day,*,actor=None):
        self._require(owner,self._actor(owner,actor));return super().tickets(owner,pid,day)

    def create(self,owner,side,name,*,actor=None):
        with self._write(owner,actor) as (c,actor):
            pid=super().create(owner,side,name)
            self._audit(c,owner,actor,'create_profile',pid,new=json.dumps({'side':side,'name':name},ensure_ascii=False));return pid

    def configure(self,owner,pid,field,text,*,actor=None):
        with self._write(owner,actor) as (c,actor):
            old=json.dumps(super().profile(owner,pid)['config'],ensure_ascii=False)
            super().configure(owner,pid,field,text)
            new=json.dumps(super().profile(owner,pid)['config'],ensure_ascii=False)
            self._audit(c,owner,actor,'configure_'+field,pid,old,new)

    def select_variant(self,owner,pid,variant,*,actor=None):
        with self._write(owner,actor) as (c,actor):
            old=json.dumps(super().profile(owner,pid)['config'],ensure_ascii=False)
            super().select_variant(owner,pid,variant)
            self._audit(c,owner,actor,'select_variant',pid,old,json.dumps(super().profile(owner,pid)['config'],ensure_ascii=False))

    def set_old_balance(self,owner,pid,text,*,actor=None):
        # Same accepted syntax and exact signed Decimal as Ledger; only storage
        # ownership/actor authorization changes. No arithmetic is introduced.
        raw=text.strip().upper()
        if raw=='0':amount=Decimal(0)
        else:
            match=re.fullmatch(r'(THU|TRẢ|TRA)\s+([0-9]+(?:,[0-9]+)?)',raw)
            if not match:raise ValueError('Gửi THU 2356, TRẢ 2356 hoặc 0. Tiền tính bằng k; số lẻ dùng dấu phẩy, không dùng dấu chấm.')
            amount=number(match[2])
            if match[1]!='THU':amount=amount.copy_negate()
        with self._write(owner,actor) as (c,actor):
            p=super().profile(owner,pid)
            c.execute('UPDATE profiles SET old_balance=? WHERE owner=? AND id=?',(str(amount),owner,pid))
            c.execute('INSERT INTO balance_audit(profile,actor,at,old_amount,new_amount) VALUES(?,?,?,?,?)',
                      (pid,actor,datetime.now(timezone.utc).isoformat(),p['old_balance'],str(amount)))
            self._audit(c,owner,actor,'old_balance',pid,p['old_balance'],str(amount))

    def day(self,owner,actor,initial):
        self._require(owner,actor)
        rows=self.query('SELECT day FROM workspace_state WHERE workspace_owner=?',(owner,))
        if rows:return rows[0]['day']
        with self._write(owner,actor) as (c,actor):
            c.execute('INSERT INTO workspace_state VALUES(?,?) ON CONFLICT(workspace_owner) DO NOTHING',(owner,initial))
            return c.execute('SELECT day FROM workspace_state WHERE workspace_owner=?',(owner,)).fetchone()[0]

    def set_day(self,owner,actor,day):
        if datetime.strptime(day,'%d-%m-%Y').strftime('%d-%m-%Y')!=day:raise ValueError('Ngày không hợp lệ.')
        with self._write(owner,actor) as (c,actor):
            old=c.execute('SELECT day FROM workspace_state WHERE workspace_owner=?',(owner,)).fetchone()
            c.execute('INSERT INTO workspace_state VALUES(?,?) ON CONFLICT(workspace_owner) DO UPDATE SET day=excluded.day',(owner,day))
            self._audit(c,owner,actor,'day',old=old[0] if old else None,new=day)

    def add(self,owner,pid,day,message,raw,*,actor=None,expected_config=None):
        actor=self._actor(owner,actor)
        if datetime.strptime(day,'%d-%m-%Y').strftime('%d-%m-%Y')!=day:raise ValueError('Ngày không hợp lệ.')
        parsed=checked_calculation(raw)
        with self._write(owner,actor) as (c,actor):
            p=super().profile(owner,pid)
            if expected_config is not None and p['config']!=expected_config:raise ValueError('Tỷ lệ của bảng vừa đổi. Chưa lưu tin. Chọn lại bảng, kiểm tra tỷ lệ rồi gửi lại.')
            if not p['config']['ready']:raise ValueError('Hãy lưu % trước khi nhập tin (có thể nhập toàn số 0).')
            validate_config(p['config'])
            if c.execute('SELECT 1 FROM telegram_messages WHERE workspace_owner=? AND actor=? AND message=?',(owner,actor,message)).fetchone():return False
            # Keep historical OWNER message keys exactly as before. Staff use
            # negative internal keys; actual sender/message identity is retained
            # separately. Telegram message IDs are positive and chat-scoped.
            key=message if actor==owner else c.execute('SELECT MIN(message) FROM tickets WHERE owner=?',(owner,)).fetchone()[0]
            if actor!=owner:key=min(0,key or 0)-1
            cur=c.execute('INSERT INTO tickets(owner,profile,day,message,raw,config,entries_snapshot) VALUES(?,?,?,?,?,?,?) ON CONFLICT(owner,message) DO NOTHING',
                          (owner,pid,day,key,raw,json.dumps(p['config'],ensure_ascii=False),snapshot(parsed)))
            if not cur.rowcount:return False
            c.execute('INSERT INTO telegram_messages VALUES(?,?,?,?)',(owner,actor,message,cur.lastrowid))
            self._audit(c,owner,actor,'add_ticket',cur.lastrowid,new=raw)
            return True

    def message_ticket(self,owner,actor,message):
        self._require(owner,actor)
        rows=self.query('SELECT ticket AS id FROM telegram_messages WHERE workspace_owner=? AND actor=? AND message=?',(owner,actor,message))
        if rows:return rows[0]['id']
        # Historical OWNER tickets predate the identity table.
        if actor==owner:
            rows=self.query('SELECT id FROM tickets WHERE owner=? AND message=?',(owner,message))
            if rows:return rows[0]['id']
        raise ValueError('Không tìm thấy tin đã lưu.')

    def replace(self,owner,pid,day,tid,raw,*,actor=None,expected_revision=None):
        self._change_ticket(owner,pid,day,tid,raw,actor,expected_revision)
    def delete(self,owner,pid,day,tid,*,actor=None,expected_revision=None):
        self._change_ticket(owner,pid,day,tid,None,actor,expected_revision)
    def _change_ticket(self,owner,pid,day,tid,raw,actor,expected_revision):
        actor=self._actor(owner,actor)
        if actor!=owner and expected_revision is None:raise ValueError('Cần bản đang xem của vé để sửa/xóa. Mở lại Sửa tin/Xóa tin.')
        parsed=checked_calculation(raw) if raw is not None else None
        with self._write(owner,actor) as (c,actor):
            row=c.execute('SELECT raw,revision FROM tickets WHERE owner=? AND profile=? AND day=? AND id=? AND deleted_at IS NULL',(owner,pid,day,tid)).fetchone()
            if not row or (expected_revision is not None and row['revision']!=expected_revision):raise ValueError('Vé đã thay đổi/xóa hoặc không thuộc bảng/ngày này. Mở lại Sửa tin/Xóa tin.')
            at=datetime.now(timezone.utc).isoformat()
            if raw is None:c.execute('UPDATE tickets SET deleted_at=?,revision=revision+1 WHERE id=?',(at,tid))
            else:c.execute('UPDATE tickets SET raw=?,entries_snapshot=?,revision=revision+1 WHERE id=?',(raw,snapshot(parsed),tid))
            c.execute('INSERT INTO ticket_audit(ticket,actor,action,at,old_raw,new_raw) VALUES(?,?,?,?,?,?)',
                      (tid,actor,'delete' if raw is None else 'edit',at,row['raw'],raw))
            self._audit(c,owner,actor,'delete_ticket' if raw is None else 'edit_ticket',tid,row['raw'],raw)
