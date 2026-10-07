"""Multi-user authorization/storage and real handler regressions; offline only."""
import asyncio
import importlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from accounting import Ledger, totals
from presentation import render_summary
from results import LotteryResult
from workspace import WorkspaceLedger, user_ids

OWNER=1001;A=2002;B=3003;DAY='06-10-2026'
RESULT=LotteryResult(DAY,'12312',tuple(['12','34']+['00']*25),0)

class MultiUserStorageTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.db=WorkspaceLedger(self.tmp.name+'/db')
        self.pid=self.db.create(OWNER,'Khách','HUO');self.db.configure(OWNER,self.pid,'percent','5;0;0;0;0')
    def tearDown(self):self.tmp.cleanup()
    def grant(self):self.db.add_users(OWNER,OWNER,f'{A} {B}')
    def add(self,actor=OWNER,message=1,raw='Đề 99=100'):
        self.db.add(OWNER,self.pid,DAY,message,raw,actor=actor)
        return self.db.tickets(OWNER,self.pid,DAY)[-1]
    def test_owner_implicit_authorization(self):self.assertTrue(self.db.authorized(OWNER,OWNER));self.assertEqual(self.db.users(OWNER,OWNER),[])
    def test_unauthorized_default(self):self.assertFalse(self.db.authorized(OWNER,A))
    def test_add_single(self):self.assertEqual(self.db.add_users(OWNER,OWNER,str(A)),([A],[]));self.assertTrue(self.db.authorized(OWNER,A))
    def test_add_newlines(self):self.assertEqual(self.db.add_users(OWNER,OWNER,f'{A}\n{B}')[0],[A,B])
    def test_add_commas(self):self.assertEqual(self.db.add_users(OWNER,OWNER,f'{A}, {B}')[0],[A,B])
    def test_add_spaces(self):self.assertEqual(self.db.add_users(OWNER,OWNER,f'{A} {B}')[0],[A,B])
    def test_add_duplicates(self):
        self.db.add_users(OWNER,OWNER,str(A));self.assertEqual(self.db.add_users(OWNER,OWNER,f'{A} {B} {B}'),([B],[A]));self.assertEqual(self.db.users(OWNER,OWNER),[A,B])
    def test_owner_not_inserted(self):self.assertEqual(self.db.add_users(OWNER,OWNER,str(OWNER)),([],[OWNER]));self.assertEqual(self.db.users(OWNER,OWNER),[])
    def test_invalid_ids(self):
        for raw in ['abc','@abc','-123','0','1.2','١','9223372036854775808','123;456','']:
            with self.assertRaises(ValueError):self.db.add_users(OWNER,OWNER,raw)
        self.assertEqual(self.db.users(OWNER,OWNER),[])
    def test_mixed_batch_atomic(self):
        with self.assertRaises(ValueError) as caught:self.db.add_users(OWNER,OWNER,f'{A}\nabc\n{B}\n-123')
        self.assertIn('Hợp lệ:',str(caught.exception));self.assertIn('Không hợp lệ:',str(caught.exception));self.assertIn(str(A),str(caught.exception));self.assertEqual(self.db.users(OWNER,OWNER),[])
    def test_regular_cannot_grant(self):
        self.grant()
        with self.assertRaises(ValueError):self.db.add_users(OWNER,A,'4004')
        self.assertFalse(self.db.authorized(OWNER,4004))
    def test_regular_cannot_list_users(self):
        self.grant()
        with self.assertRaises(ValueError):self.db.users(OWNER,A)
    def test_remove_requires_confirmation(self):
        self.grant()
        with self.assertRaises(ValueError):self.db.remove_users(OWNER,OWNER,str(A))
        self.assertTrue(self.db.authorized(OWNER,A))
    def test_remove_single_immediate(self):
        self.grant();self.assertEqual(self.db.remove_users(OWNER,OWNER,str(A),confirmed=True),([A],[]));self.assertFalse(self.db.authorized(OWNER,A))
    def test_remove_batch(self):
        self.grant();self.db.remove_users(OWNER,OWNER,f'{A}\n{B}',confirmed=True);self.assertEqual(self.db.users(OWNER,OWNER),[])
    def test_remove_owner_atomic_reject(self):
        self.grant()
        with self.assertRaises(ValueError):self.db.remove_users(OWNER,OWNER,f'{A} {OWNER}',confirmed=True)
        self.assertTrue(self.db.authorized(OWNER,A));self.assertTrue(self.db.authorized(OWNER,OWNER))
    def test_remove_invalid_atomic(self):
        self.grant()
        with self.assertRaises(ValueError):self.db.remove_users(OWNER,OWNER,f'{A} abc',confirmed=True)
        self.assertTrue(self.db.authorized(OWNER,A))
    def test_regular_cannot_revoke(self):
        self.grant()
        with self.assertRaises(ValueError):self.db.remove_users(OWNER,A,str(B),confirmed=True)
        self.assertTrue(self.db.authorized(OWNER,B))
    def test_permissions_persist(self):self.grant();self.assertTrue(WorkspaceLedger(self.db.path).authorized(OWNER,A))
    def test_grant_workspace_isolation(self):self.grant();self.assertFalse(self.db.authorized(4004,A))
    def test_unauthorized_cannot_read(self):
        for action in [lambda:self.db.profile(OWNER,self.pid,actor=A),lambda:self.db.profiles(OWNER,actor=A),lambda:self.db.tickets(OWNER,self.pid,DAY,actor=A)]:
            with self.assertRaises(ValueError):action()
    def test_unauthorized_cannot_write(self):
        actions=[lambda:self.db.create(OWNER,'Khách','OTHER',actor=A),lambda:self.db.configure(OWNER,self.pid,'percent','0;0;0;0;0',actor=A),lambda:self.db.set_old_balance(OWNER,self.pid,'THU 100',actor=A),lambda:self.db.add(OWNER,self.pid,DAY,1,'Đề 99=100',actor=A)]
        for action in actions:
            with self.assertRaises(ValueError):action()
        self.assertEqual(len(self.db.profiles(OWNER)),1);self.assertEqual(self.db.profile(OWNER,self.pid)['old_balance'],'0');self.assertEqual(self.db.tickets(OWNER,self.pid,DAY),[])
    def test_owner_profile_visible_to_staff(self):self.grant();self.assertEqual(self.db.profiles(OWNER,actor=A)[0]['id'],self.pid)
    def test_staff_ticket_visible_to_owner(self):
        self.grant();self.add(A);rows=self.db.tickets(OWNER,self.pid,DAY);self.assertEqual(rows[0]['owner'],OWNER);self.assertEqual(totals(rows)['Đề'][0],100)
    def test_staff_create_uses_owner_namespace(self):
        self.grant();pid=self.db.create(OWNER,'Chủ','MASTER',actor=A);self.assertEqual(self.db.profile(OWNER,pid)['owner'],OWNER);self.assertEqual(self.db.profiles(A),[])
    def test_staff_edit_visible_to_other_staff(self):
        self.grant();row=self.add(A);self.db.replace(OWNER,self.pid,DAY,row['id'],'Đề 99=200',actor=B,expected_revision=row['revision'])
        self.assertEqual(self.db.tickets(OWNER,self.pid,DAY,actor=A)[0]['raw'],'Đề 99=200')
    def test_shared_debt(self):
        self.grant();self.db.set_old_balance(OWNER,self.pid,'TRẢ 200',actor=A);self.assertEqual(self.db.profile(OWNER,self.pid,actor=B)['old_balance'],'-200')
    def test_shared_percent(self):
        self.grant();self.db.configure(OWNER,self.pid,'percent','10;0;0;0;0',actor=A);self.assertEqual(self.db.profile(OWNER,self.pid,actor=B)['config']['percent']['Đề'],'10')
    def test_shared_totals(self):
        self.grant();self.add(A);p=self.db.profile(OWNER,self.pid);self.assertEqual(render_summary(p,DAY,self.db.tickets(OWNER,self.pid,DAY,actor=A),RESULT),render_summary(p,DAY,self.db.tickets(OWNER,self.pid,DAY,actor=B),RESULT))
    def test_shared_day_persisted(self):
        self.grant();self.assertEqual(self.db.day(OWNER,A,DAY),DAY);self.db.set_day(OWNER,B,'07-10-2026');self.assertEqual(WorkspaceLedger(self.db.path).day(OWNER,OWNER,DAY),'07-10-2026')
    def test_same_message_ids_two_chats_not_duplicate(self):
        self.grant();self.add(OWNER,1);self.add(A,1);self.add(B,1);self.assertEqual(len(self.db.tickets(OWNER,self.pid,DAY)),3)
    def test_staff_duplicate_no_double_count(self):
        self.grant();self.add(A,1);self.assertFalse(self.db.add(OWNER,self.pid,DAY,1,'Đề 99=100',actor=A));self.assertEqual(len(self.db.tickets(OWNER,self.pid,DAY)),1)
    def test_deleted_staff_message_cannot_resurrect(self):
        self.grant();row=self.add(A);self.db.delete(OWNER,self.pid,DAY,row['id'],actor=B,expected_revision=0)
        self.assertFalse(self.db.add(OWNER,self.pid,DAY,1,'Đề 99=100',actor=A));self.assertFalse(self.db.tickets(OWNER,self.pid,DAY))
    def test_legacy_owner_duplicate_retained(self):
        legacy=Ledger(self.tmp.name+'/legacy');pid=legacy.create(OWNER,'Khách','OLD');legacy.configure(OWNER,pid,'percent','0;0;0;0;0');legacy.add(OWNER,pid,DAY,10,'Đề 99=100')
        db=WorkspaceLedger(legacy.path);self.assertFalse(db.add(OWNER,pid,DAY,10,'Đề 99=100'));self.assertEqual(db.message_ticket(OWNER,OWNER,10),1)
    def test_revoked_user_cannot_mutate_existing_ticket(self):
        self.grant();row=self.add(A);self.db.remove_users(OWNER,OWNER,str(A),confirmed=True)
        with self.assertRaises(ValueError):self.db.replace(OWNER,self.pid,DAY,row['id'],'Đề 99=200',actor=A,expected_revision=0)
        self.assertEqual(self.db.tickets(OWNER,self.pid,DAY)[0]['raw'],'Đề 99=100')
    def test_edit_audit_actor_and_owner(self):
        self.grant();row=self.add();self.db.replace(OWNER,self.pid,DAY,row['id'],'Đề 99=200',actor=A,expected_revision=0)
        self.assertEqual(self.db.query('SELECT actor FROM ticket_audit')[0]['actor'],A);self.assertEqual(self.db.tickets(OWNER,self.pid,DAY)[0]['owner'],OWNER)
    def test_delete_audit_actor(self):
        self.grant();row=self.add();self.db.delete(OWNER,self.pid,DAY,row['id'],actor=A,expected_revision=0);self.assertEqual(self.db.query('SELECT actor FROM ticket_audit')[0]['actor'],A)
    def test_debt_audit_actor(self):
        self.grant();self.db.set_old_balance(OWNER,self.pid,'THU 100',actor=A);self.assertEqual(self.db.query('SELECT actor FROM balance_audit')[0]['actor'],A)
    def test_config_reward_variant_audit_actor(self):
        self.grant();self.db.configure(OWNER,self.pid,'reward','90;3,5;15;48;180;400;10',actor=A);self.db.select_variant(OWNER,self.pid,'14',actor=B)
        rows=self.db.query("SELECT * FROM workspace_audit WHERE action IN ('configure_reward','select_variant')")
        self.assertEqual([r['actor'] for r in rows],[A,B]);self.assertTrue(all(r['workspace_owner']==OWNER for r in rows))
    def test_grant_revoke_audit_actor(self):
        self.grant();self.db.remove_users(OWNER,OWNER,str(A),confirmed=True);rows=self.db.query("SELECT * FROM workspace_audit WHERE action IN ('grant','revoke')")
        self.assertEqual(len(rows),3);self.assertTrue(all(r['actor']==OWNER and r['at'] for r in rows))
    def test_snapshot_equivalence_with_original_ledger(self):
        legacy=Ledger(self.tmp.name+'/reference');pid=legacy.create(OWNER,'Khách','HUO');legacy.configure(OWNER,pid,'percent','5;0;0;0;0');legacy.add(OWNER,pid,DAY,1,'Đề 99=100');row=self.add()
        expected=legacy.tickets(OWNER,pid,DAY)[0]
        self.assertEqual(row['config'],expected['config']);self.assertEqual(row['entries_snapshot'],expected['entries_snapshot']);self.assertEqual(totals([row],RESULT),totals([expected],RESULT))
    def test_all_category_snapshots_and_payouts_match_original(self):
        self.grant();legacy=Ledger(self.tmp.name+'/allref');pid=legacy.create(OWNER,'Khách','REF');legacy.configure(OWNER,pid,'percent','5;0;0;0;0')
        for mid,text in enumerate(['Đề 12=1tr5','Bao 12=10','X 12-34=10','X3 12-34-00=10','X4 12-34-00-99=10','Càng 312.412=10'],1):
            legacy.add(OWNER,pid,DAY,mid,text);self.db.add(OWNER,self.pid,DAY,mid,text,actor=A)
        expected=legacy.tickets(OWNER,pid,DAY);actual=self.db.tickets(OWNER,self.pid,DAY)
        self.assertEqual([r['entries_snapshot'] for r in actual],[r['entries_snapshot'] for r in expected]);self.assertEqual(totals(actual,RESULT),totals(expected,RESULT))
    def test_staff_edit_retains_snapshot_config(self):
        self.grant();row=self.add();self.db.configure(OWNER,self.pid,'percent','20;0;0;0;0',actor=B);self.db.replace(OWNER,self.pid,DAY,row['id'],'Đề 99=200',actor=A,expected_revision=0)
        self.assertEqual(self.db.tickets(OWNER,self.pid,DAY)[0]['config'],row['config'])
    def test_debt_semantics_identical_to_original(self):
        legacy=Ledger(self.tmp.name+'/debtref');pid=legacy.create(OWNER,'Khách','REF')
        for text in ['THU 2356','TRẢ 200','THU 0,1','0']:
            self.db.set_old_balance(OWNER,self.pid,text);legacy.set_old_balance(OWNER,pid,text);self.assertEqual(self.db.profile(OWNER,self.pid)['old_balance'],legacy.profile(OWNER,pid)['old_balance'])
    def test_stale_revision_rejects_even_same_raw(self):
        self.grant();row=self.add();self.db.replace(OWNER,self.pid,DAY,row['id'],row['raw'],actor=A,expected_revision=0)
        with self.assertRaises(ValueError):self.db.replace(OWNER,self.pid,DAY,row['id'],'Đề 99=200',actor=B,expected_revision=0)
    def test_concurrent_edit_one_wins(self):self.concurrent('edit','edit')
    def test_concurrent_edit_delete_one_wins(self):self.concurrent('edit','delete')
    def test_concurrent_delete_one_wins(self):self.concurrent('delete','delete')
    def concurrent(self,first,second):
        self.grant();row=self.add();barrier=Barrier(2)
        def action(actor,kind):
            barrier.wait()
            try:
                if kind=='edit':self.db.replace(OWNER,self.pid,DAY,row['id'],'Đề 99=200',actor=actor,expected_revision=0)
                else:self.db.delete(OWNER,self.pid,DAY,row['id'],actor=actor,expected_revision=0)
                return 'win'
            except ValueError as error:
                self.assertIn('Vé đã thay đổi/xóa',str(error));return 'stale'
        with ThreadPoolExecutor(2) as pool:
            futures=[pool.submit(action,A,first),pool.submit(action,B,second)];self.assertEqual(sorted(f.result() for f in futures),['stale','win'])
        self.assertEqual(len(self.db.query('SELECT * FROM ticket_audit')),1)
    def test_concurrent_duplicate_one_stored(self):
        self.grant();barrier=Barrier(2)
        def add():barrier.wait();return self.db.add(OWNER,self.pid,DAY,1,'Đề 99=100',actor=A)
        with ThreadPoolExecutor(2) as pool:
            futures=[pool.submit(add),pool.submit(add)];self.assertEqual(sorted(f.result() for f in futures),[False,True])
    def test_changed_config_rejected_inside_add_transaction(self):
        self.grant();old=self.db.profile(OWNER,self.pid)['config'];self.db.configure(OWNER,self.pid,'percent','20;0;0;0;0',actor=B)
        with self.assertRaises(ValueError):self.db.add(OWNER,self.pid,DAY,1,'Đề 99=100',actor=A,expected_config=old)
        self.assertFalse(self.db.tickets(OWNER,self.pid,DAY))
    def test_atomic_config_error_no_audit(self):
        self.grant();before=self.db.profile(OWNER,self.pid);count=len(self.db.query('SELECT * FROM workspace_audit'))
        with self.assertRaises(ValueError):self.db.configure(OWNER,self.pid,'reward','90;3,5;16;48;180;400;10',actor=A)
        self.assertEqual(self.db.profile(OWNER,self.pid),before);self.assertEqual(len(self.db.query('SELECT * FROM workspace_audit')),count)

class MultiUserUITests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.env=patch.dict(os.environ,{'BOT_DB':self.tmp.name+'/db','TELEGRAM_ADMIN_ID':str(OWNER)})
        self.env.start();self.previous=sys.modules.pop('bot',None);self.bot=importlib.import_module('bot')
        self.pid=self.bot.DB.create(OWNER,'Khách','HUO');self.bot.DB.configure(OWNER,self.pid,'percent','0;0;0;0;0')
        self.bot.DB.add_users(OWNER,OWNER,f'{A} {B}');self.outputs={};self.contexts={};self.sequence={}
        for uid in [OWNER,A,B,4004]:self.contexts[uid]=SimpleNamespace(user_data={'profile':self.pid,'day':DAY});self.outputs[uid]=[];self.sequence[uid]=0
    def tearDown(self):
        sys.modules.pop('bot',None)
        if self.previous is not None:sys.modules['bot']=self.previous
        self.env.stop();self.tmp.cleanup()
    async def send(self,uid,text,chat='private'):
        self.sequence[uid]+=1
        async def reply(value,**kwargs):self.outputs[uid].append((value,kwargs))
        update=SimpleNamespace(effective_user=SimpleNamespace(id=uid),effective_chat=SimpleNamespace(type=chat),effective_message=SimpleNamespace(text=text,message_id=self.sequence[uid],reply_text=reply))
        await self.bot.handle(update,self.contexts[uid]);return update
    def test_owner_menu_only(self):
        async def flow():
            for uid in [OWNER,A]:
                update=await self.send(uid,'Hủy');await self.bot.start(update,self.contexts[uid])
                labels=[b.text for row in self.outputs[uid][-1][1]['reply_markup'].keyboard for b in row]
                self.assertEqual('👥 Người sử dụng' in labels,uid==OWNER)
        asyncio.run(flow())
    def test_owner_list_includes_owner_and_count(self):
        async def flow():await self.send(OWNER,'👥 Người sử dụng');self.assertIn('👑 OWNER: '+str(OWNER),self.outputs[OWNER][-1][0]);self.assertIn('Tổng: 3 người',self.outputs[OWNER][-1][0])
        asyncio.run(flow())
    def test_owner_batch_add_flow(self):
        async def flow():await self.send(OWNER,'➕ Thêm người');await self.send(OWNER,'4004\n5005, 6006');self.assertIn('Thêm mới: 3',self.outputs[OWNER][-1][0]);self.assertTrue(self.bot.DB.authorized(OWNER,6006))
        asyncio.run(flow())
    def test_owner_invalid_batch_no_add(self):
        async def flow():await self.send(OWNER,'➕ Thêm người');await self.send(OWNER,'4004 abc');self.assertIn('Không hợp lệ',self.outputs[OWNER][-1][0]);self.assertFalse(self.bot.DB.authorized(OWNER,4004))
        asyncio.run(flow())
    def test_owner_remove_only_after_confirmation(self):
        async def flow():
            await self.send(OWNER,'➖ Xóa người');await self.send(OWNER,f'{A} {B}');self.assertTrue(self.bot.DB.authorized(OWNER,A));self.assertIn('XÓA QUYỀN',self.outputs[OWNER][-1][0])
            await self.send(OWNER,'XÓA QUYỀN');self.assertFalse(self.bot.DB.authorized(OWNER,A));self.assertFalse(self.bot.DB.authorized(OWNER,B))
        asyncio.run(flow())
    def test_owner_remove_cancel(self):
        async def flow():await self.send(OWNER,'➖ Xóa người');await self.send(OWNER,str(A));await self.send(OWNER,'Hủy');self.assertTrue(self.bot.DB.authorized(OWNER,A))
        asyncio.run(flow())
    def test_regular_forged_management_block(self):
        async def flow():
            for text in ['👥 Người sử dụng','➕ Thêm người','➖ Xóa người','📋 Danh sách','XÓA QUYỀN']:
                await self.send(A,text);self.assertIn('Chỉ OWNER',self.outputs[A][-1][0])
        asyncio.run(flow());self.assertEqual(self.bot.DB.users(OWNER,OWNER),[A,B])
    def test_unauthorized_read_and_write_block(self):
        async def flow():
            for text in ['Sổ vé','Xem tổng','Xem raw','Nợ cũ','Đề 99=100','Tạo người','👥 Người sử dụng']:await self.send(4004,text)
        asyncio.run(flow());self.assertEqual(self.outputs[4004],[]);self.assertFalse(self.bot.DB.tickets(OWNER,self.pid,DAY))
    def test_group_owner_and_staff_block(self):
        async def flow():
            for uid in [OWNER,A]:await self.send(uid,'Đề 99=100','group');self.assertEqual(self.outputs[uid],[])
        asyncio.run(flow());self.assertFalse(self.bot.DB.tickets(OWNER,self.pid,DAY))
    def test_staff_sees_owner_profile_and_adds_to_shared_book(self):
        async def flow():await self.send(A,'Nhập tin');self.assertIn('HUO',self.outputs[A][-1][0]);await self.send(A,'HUO');await self.send(A,'Đề 99=100');await self.send(OWNER,'Sổ vé');self.assertIn('Đề: 100k',self.outputs[OWNER][-1][0])
        asyncio.run(flow());self.assertEqual(self.bot.DB.tickets(OWNER,self.pid,DAY)[0]['owner'],OWNER)
    def test_staff_b_confirmation_preserves_actor_message(self):
        async def flow():
            await self.send(A,'B91=175k');self.assertFalse(self.bot.DB.tickets(OWNER,self.pid,DAY));await self.send(A,'BAO TOÀN BỘ');self.assertEqual(len(self.bot.DB.tickets(OWNER,self.pid,DAY)),1)
            self.assertEqual(self.bot.DB.message_ticket(OWNER,A,1),1)
        asyncio.run(flow())
    def test_revoked_user_pending_choice_cannot_store(self):
        async def flow():await self.send(A,'B91=175k');self.bot.DB.remove_users(OWNER,OWNER,str(A),confirmed=True);await self.send(A,'BAO TOÀN BỘ')
        asyncio.run(flow());self.assertFalse(self.bot.DB.tickets(OWNER,self.pid,DAY))
    def test_sessions_selected_profile_independent(self):
        other=self.bot.DB.create(OWNER,'Khách','ABC');self.bot.DB.configure(OWNER,other,'percent','0;0;0;0;0')
        async def flow():await self.send(A,'Nhập tin');await self.send(A,'ABC');await self.send(B,'Đề 99=100')
        asyncio.run(flow());self.assertEqual(self.contexts[A].user_data['profile'],other);self.assertEqual(self.contexts[B].user_data['profile'],self.pid);self.assertFalse(self.bot.DB.tickets(OWNER,other,DAY))
    def test_shared_day_change_cancels_other_pending(self):
        async def flow():
            await self.send(A,'B91=175k');await self.send(OWNER,'Đổi ngày');await self.send(OWNER,'07-10-2026');await self.send(A,'BAO TOÀN BỘ')
            self.assertIn('Ngày chung đã đổi',self.outputs[A][-1][0]);self.assertNotIn('pending_b',self.contexts[A].user_data);self.assertEqual(self.contexts[A].user_data['day'],'07-10-2026')
        asyncio.run(flow());self.assertFalse(self.bot.DB.query('SELECT * FROM tickets'))
    def test_ui_staff_edit_actor(self):
        async def flow():
            await self.send(OWNER,'Đề 99=100');await self.send(A,'Sửa tin');await self.send(A,'1; Đề 99=200');await self.send(B,'Sổ vé');self.assertIn('Đề: 200k',self.outputs[B][-1][0])
        asyncio.run(flow());self.assertEqual(self.bot.DB.query('SELECT actor FROM ticket_audit')[0]['actor'],A)
    def test_ui_stale_edit_second_gets_warning(self):
        async def flow():
            await self.send(OWNER,'Đề 99=100');await self.send(A,'Sửa tin');await self.send(B,'Sửa tin');await self.send(A,'1; Đề 99=200');await self.send(B,'1; Đề 99=300');self.assertIn('Vé đã thay đổi/xóa',self.outputs[B][-1][0])
        asyncio.run(flow());self.assertEqual(self.bot.DB.tickets(OWNER,self.pid,DAY)[0]['raw'],'Đề 99=200')
    def test_ui_staff_delete_actor_and_confirm(self):
        async def flow():
            await self.send(OWNER,'Đề 99=100');await self.send(A,'Xóa tin');await self.send(A,'1');self.assertTrue(self.bot.DB.tickets(OWNER,self.pid,DAY));await self.send(A,'XÓA');self.assertFalse(self.bot.DB.tickets(OWNER,self.pid,DAY))
        asyncio.run(flow());self.assertEqual(self.bot.DB.query('SELECT actor FROM ticket_audit')[0]['actor'],A)
    def test_ui_staff_debt_percent_reward_actor(self):
        async def flow():
            await self.send(A,'Nợ cũ');await self.send(A,'THU 100');await self.send(A,'Sửa %');await self.send(A,'5;0;0;0;0');await self.send(B,'Sửa thưởng');await self.send(B,'90;3,5;15;48;180;400;10')
        asyncio.run(flow());self.assertEqual(self.bot.DB.query('SELECT actor FROM balance_audit')[0]['actor'],A)
        rows=self.bot.DB.query("SELECT actor FROM workspace_audit WHERE action='configure_reward'");self.assertEqual(rows[-1]['actor'],B)
    def test_changed_profile_config_warns_before_new_ticket(self):
        async def flow():
            await self.send(A,'Nhập tin');await self.send(A,'HUO');await self.send(B,'Sửa %');await self.send(B,'5;0;0;0;0');await self.send(A,'Đề 99=100')
            self.assertIn('Tỷ lệ của bảng vừa',self.outputs[A][-1][0]);self.assertFalse(self.bot.DB.tickets(OWNER,self.pid,DAY))
            await self.send(A,'Đề 99=100');self.assertEqual(len(self.bot.DB.tickets(OWNER,self.pid,DAY)),1)
        asyncio.run(flow())
    def test_variant_switch_warns_other_user_before_save(self):
        async def flow():
            await self.send(A,'Nhập tin');await self.send(A,'HUO');await self.send(B,'Xiên ×14');await self.send(B,'Sửa %');await self.send(B,'0;0;0;0;0');await self.send(A,'X 12-34=10')
            self.assertIn('Chưa lưu tin',self.outputs[A][-1][0]);self.assertFalse(self.bot.DB.tickets(OWNER,self.pid,DAY))
        asyncio.run(flow())
    def test_ui_totals_shared(self):
        async def flow():
            await self.send(A,'Đề 99=100')
            with patch.object(self.bot,'fetch_latest_result',return_value=RESULT):
                await self.send(OWNER,'Xem tổng');await self.send(B,'Xem tổng')
            self.assertEqual(self.outputs[OWNER][-1][0],self.outputs[B][-1][0])
        asyncio.run(flow())
    def test_raw_shared_but_revocation_blocks_reply(self):
        async def flow():
            await self.send(A,'Đề 99=100');await self.send(B,'Xem raw');await self.send(B,'1');self.assertIn('Đề 99=100',self.outputs[B][-1][0])
            before=len(self.outputs[B]);self.bot.DB.remove_users(OWNER,OWNER,str(B),confirmed=True);await self.send(B,'Sổ vé');self.assertEqual(len(self.outputs[B]),before)
        asyncio.run(flow())

if __name__=='__main__':unittest.main()
