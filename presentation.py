"""Phone-friendly views over stored entries. Never parse raw tickets."""
import json
from decimal import Decimal, Inexact, ROUND_HALF_UP, localcontext
from accounting import number, stored_entries, totals, validate_config, validate_result
from calculator import exact_decimal, format_amount
from results import _winning_for_entry


def display_k(value):
    with localcontext() as context:
        context.prec = 80
        context.traps[Inexact] = False
        rounded = value.quantize(Decimal('1'), rounding=ROUND_HALF_UP)
    return format_amount(rounded)


def _active_rows(profile, day, rows):
    if any(r['owner'] != profile['owner'] or r['profile'] != profile['id'] or r['day'] != day for r in rows):
        raise ValueError('Dữ liệu vé không thuộc bảng/ngày đang chọn.')
    return [r for r in rows if not r.get('deleted_at')]


@exact_decimal
def _reward_lines(rows, result):
    # Display winning base from the same matcher and each ticket's factor.
    # Do not infer a base by dividing payout by today's profile factor.
    grouped = {}
    aliases = {'Đề':'Đề', 'Bao':'Bao', 'Xiên 2':'X2', 'Xiên 3':'X3',
               'Xiên 4':'X4', 'Càng':'C', 'Áp càng':'AC'}
    def add(kind, base, cfg):
        if not base:
            return
        factor = number(cfg['reward'][kind])
        key = (kind, factor if kind in ('Xiên 2','Xiên 3','Áp càng') else None)
        value = grouped.setdefault(key, [Decimal(0),Decimal(0)])
        value[0] += base
        value[1] += base * factor
    for row in rows:
        cfg = json.loads(row['config'])
        validate_config(cfg)
        for entry in stored_entries(row):
            if entry.kind == 'Càng':
                exact = sum(n == result.cang_number for n in entry.numbers)
                ap = sum(n != result.cang_number and n[-2:] == result.de_number for n in entry.numbers)
                add('Càng', entry.unit_stake * exact, cfg)
                add('Áp càng', entry.unit_stake * ap, cfg)
            else:
                base, _, _, _ = _winning_for_entry(entry, result)
                add(entry.kind, base, cfg)
    lines = []
    for kind in ('Đề','Bao','Xiên 2','Xiên 3','Xiên 4','Áp càng','Càng'):
        for (item, factor), (base, payout) in grouped.items():
            if item != kind:
                continue
            label = aliases[kind]
            factor_text = format_amount(factor).removesuffix('k') if factor is not None else ''
            if kind in ('Xiên 3','Áp càng'):
                lines.append(f'{label}: {format_amount(base)} (gốc ×{factor_text} = {format_amount(payout)} tính vào tổng thưởng)')
            else:
                if kind == 'Xiên 2':
                    label += f' ×{factor_text}'
                lines.append(f'{label}: {format_amount(payout)}')
    return lines, sum((value[1] for value in grouped.values()), Decimal(0))


@exact_decimal
def render_summary(profile, day, rows, result=None):
    rows = _active_rows(profile, day, rows)
    if result:
        validate_result(result, day)
    parts = totals(rows, result)
    lines = [f"{profile['side']} {profile['name']} — {day}", f'{len(rows)} tin', '']
    for kind, (goods, cut, _) in parts.items():
        if goods > 0:
            lines.append(f'- {kind}: {format_amount(goods)} | % {display_k(cut)} |')
    goods = sum((v[0] for v in parts.values()), Decimal(0))
    cut = sum((v[1] for v in parts.values()), Decimal(0))
    reward = sum((v[2] for v in parts.values()), Decimal(0))
    if result is not None:
        reward_lines, shown_reward = _reward_lines(rows, result)
        if shown_reward != reward:
            raise ValueError('Khối thưởng không khớp tổng; chưa chốt tiền.')
        lines += ['', 'THƯỞNG:'] + reward_lines if reward_lines else ['', 'THƯỞNG: Không có']
    else:
        lines += ['', 'THƯỞNG: Chưa có kết quả đúng ngày']
    lines += ['', '-------------------------------',
              f'➡️ Tổng hàng: {format_amount(goods)} | Trừ %: {display_k(cut)}']
    if result is None:
        return '\n'.join(lines + ['Chưa có kết quả đúng ngày. Chưa chốt tiền thu/trả.'])
    lines.append(f'➡️ Tổng thưởng: {format_amount(reward)}')
    # Identical daily balance to existing accounting, then explicit admin debt.
    balance = goods - cut - reward
    current = balance if profile['side'] == 'Khách' else balance.copy_negate()
    debt = number(profile.get('old_balance', '0'))
    net = current + debt
    name = profile['name']
    direction = 'THU' if net > 0 else 'TRẢ'
    final = 'Cân bằng: không thu/trả.' if net == 0 else f'{direction} {name}: {display_k(abs(net))}'
    if debt:
        current_label = 'THU' if current >= 0 else 'TRẢ'
        debt_label = 'THU' if debt > 0 else 'TRẢ'
        # Show exact signed components so display rounding cannot imply an
        # incorrect arithmetic identity when debt has fractional k.
        lines += ['', f'Hiện tại: {current_label} {name}: {format_amount(abs(current))}',
                  f'Nợ cũ: {debt_label} {format_amount(abs(debt))}',
                  'Gộp số dư chính xác rồi làm tròn đến 1k.']
    lines += ['', final]
    return '\n'.join(lines)


@exact_decimal
def render_book(profile, day, rows):
    rows = _active_rows(profile, day, rows)
    lines = [f"SỔ {profile['name']} — {day}", '']
    if not rows:
        return '\n'.join(lines + ['Chưa có tin.'])
    for row in rows:
        goods = {kind:Decimal(0) for kind in ('Đề','Bao','Xiên 2','Xiên 3','Xiên 4','Càng')}
        cfg = json.loads(row['config'])
        validate_config(cfg)
        for entry in stored_entries(row):
            goods[entry.kind] += entry.stake
        lines.append(f"ID {row['id']}")
        for kind, label in (('Đề','Đề'),('Bao','Bao'),('Xiên 2','X2'),('Xiên 3','X3'),('Xiên 4','X4'),('Càng','Càng')):
            value = format_amount(goods[kind]) if goods[kind] else '-'
            if kind == 'Xiên 2' and goods[kind]:
                value += ' ×' + format_amount(number(cfg['reward'][kind])).removesuffix('k')
            lines.append(f'{label}: {value}')
        lines += ['----------------', '']
    return '\n'.join(lines).rstrip()
