from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile,
    InputMediaPhoto
)
import edge_tts, asyncio, psycopg2, os, re
from storage import user_state
from loader import bot

DATABASE_URL = os.getenv("DATABASE_URL")
test_sessions = {}
HOME_BTN = []  # Bosh ekran tugmasi olib tashlandi

def render_text(text):
    if not text: return ""
    t = str(text)
    t = re.sub(r'\[en\](.*?)\[/en\]', r'\1', t, flags=re.DOTALL)
    t = re.sub(r'\[ru\](.*?)\[/ru\]', r'\1', t, flags=re.DOTALL)
    t = re.sub(r'\[skip\](.*?)\[/skip\]', r'\1', t, flags=re.DOTALL)
    t = re.sub(r'\[latex\](.*?)\[/latex\]', r'[\1]', t, flags=re.DOTALL)
    t = re.sub(r'\[img\](.*?)\[/img\]', '', t, flags=re.DOTALL)
    return t.strip()

def tts_clean(text):
    t = render_text(text)
    t = re.sub(r'[\U0001F000-\U0001FFFF\U00002600-\U000027BF\U0001F900-\U0001F9FF]+', ' ', t)
    t = re.sub(r'[•\*\#\|\_\~\`━\-]{2,}', ' ', t)
    return re.sub(r'\s+', ' ', t).strip()

# ── statistika (yuqori xabar) ──
def _board_text(s, result=""):
    total = len(s["questions"])
    ok, err = s["correct"], s["wrong"]
    done = ok + err
    bar = "🟩"*ok + "🟥"*err + "⬜"*max(0, min(20,total)-done)
    t = f"📊 {done}/{total} | ✅ {ok} | ❌ {err}\n{bar}"
    if result:
        t += f"\n━━━━━━━━━━━━━━\n{result}"
    return t

# ── javob tugmalari: [🔊][javob] ──
def _build_kb(a, b, c, d, tl=0):
    timer = f"⏱ {tl}s" if tl > 0 else "∞"
    rows = [[
        InlineKeyboardButton(text="🔊",      callback_data="speak_question"),
        InlineKeyboardButton(text=timer,     callback_data="noop_timer"),
        InlineKeyboardButton(text="🛑 Stop", callback_data="test_stop"),
    ]]
    for ans, cb, spk in [
        (a,"ans_A","speak_a"),(b,"ans_B","speak_b"),
        (c,"ans_C","speak_c"),(d,"ans_D","speak_d"),
    ]:
        label = str(ans) if ans else "—"
        if len(label) <= 22:
            rows.append([
                InlineKeyboardButton(text="🔊",  callback_data=spk),
                InlineKeyboardButton(text=label, callback_data=cb),
            ])
        else:
            rows.append([InlineKeyboardButton(text=label, callback_data=cb)])
            rows.append([InlineKeyboardButton(text="🔊 eshitish", callback_data=spk)])
    rows.append(HOME_BTN)
    return InlineKeyboardMarkup(inline_keyboard=rows)

async def _get_file_id(img_url):
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur  = conn.cursor()
        cur.execute("SELECT file_id FROM images WHERE name=%s", (img_url.strip(),))
        row  = cur.fetchone(); cur.close(); conn.close()
        return row[0] if row else None
    except: return None

async def _photo_for(test, user_id):
    (q,a,b,c,d,correct,expl,qtype,is_latex,img_url,audio,lang,tl) = test
    if is_latex and str(is_latex).lower() not in ("false","0","none",""):
        try:
            from latex_utils import latex_to_image as l2i
            p = l2i(q, user_id)
            if p and os.path.exists(p): return FSInputFile(p)
        except: pass
    elif img_url and str(img_url).strip() not in ("","None","nan"):
        return await _get_file_id(img_url)
    return None

# ══════════════════════════════════════════
#  IKKI XABARLI TIZIM
#  board_msg_id  — yuqori (statistika + natija)  — MATN
#  q_msg_id      — pastki (rasm + savol + tugma) — PHOTO yoki MATN
# ══════════════════════════════════════════

async def _edit_board(s, text):
    """Yuqori statistika xabarini edit qil."""
    chat = s["board_chat_id"]
    mid  = s.get("board_msg_id")
    if mid:
        try:
            await bot.edit_message_text(text=text, chat_id=chat, message_id=mid)
            return
        except Exception:
            # Edit muvaffaqiyatsiz — o'chir va yangi yuborish
            try: await bot.delete_message(chat, mid)
            except: pass
            s["board_msg_id"] = None
    try:
        nm = await bot.send_message(chat, text)
        s["board_msg_id"] = nm.message_id
    except Exception:
        pass

async def _edit_question(s, q_text, kb, photo=None):
    """Pastki savol xabarini edit qil (rasm yoki matn)."""
    chat = s["board_chat_id"]
    qmid = s.get("q_msg_id")

    if photo:
        # Caption 1024 belgi limiti
        cap = q_text[:1020] if len(q_text) > 1020 else q_text
        if s.get("q_has_photo") and qmid:
            try:
                await bot.edit_message_media(
                    chat_id=chat, message_id=qmid,
                    media=InputMediaPhoto(media=photo, caption=cap),
                    reply_markup=kb
                )
                return
            except Exception: pass
        if qmid:
            try: await bot.delete_message(chat, qmid)
            except: pass
        nm = await bot.send_photo(chat, photo, caption=cap, reply_markup=kb)
        s["q_msg_id"]    = nm.message_id
        s["q_has_photo"] = True
    else:
        if s.get("q_has_photo") and qmid:
            try: await bot.delete_message(chat, qmid)
            except: pass
            qmid = None
        if qmid:
            try:
                await bot.edit_message_text(
                    text=q_text, chat_id=chat, message_id=qmid,
                    reply_markup=kb
                )
                s["q_has_photo"] = False
                return
            except Exception:
                # Edit muvaffaqiyatsiz — eski xabarni o'chir
                try: await bot.delete_message(chat, qmid)
                except: pass
                s["q_msg_id"] = None
        try:
            nm = await bot.send_message(chat, q_text, reply_markup=kb)
            s["q_msg_id"]    = nm.message_id
            s["q_has_photo"] = False
        except Exception:
            pass

# ── test boshlash ──
async def start_test(user_id, tests, message):
    if not tests:
        await message.answer("❌ Test topilmadi"); return
    old = test_sessions.get(user_id, {})
    if old.get("timer_task"):
        try: old["timer_task"].cancel()
        except: pass
    user_state[user_id] = "in_test"

    # 1-xabar: statistika (yuqori)
    bm = await message.answer("⏳ Test yuklanmoqda...")
    # 2-xabar: savol (pastki) — keyin to'ldiriladi
    qm = await message.answer("...")

    test_sessions[user_id] = {
        "questions":   tests, "current": 0,
        "correct":     0,     "wrong":   0,
        "timer_task":  None,
        "board_chat_id": message.chat.id,
        "board_msg_id":  bm.message_id,
        "q_msg_id":      qm.message_id,
        "q_has_photo":   False,
        "voice_msgs":    [], "answered": False,
    }
    await show_question(user_id)

# ── savolni ko'rsatish ──
async def show_question(user_id, message=None):
    s = test_sessions.get(user_id)
    if not s: return
    if s.get("timer_task"):
        try: s["timer_task"].cancel()
        except: pass
        s["timer_task"] = None
    s["answered"] = False

    chat = s["board_chat_id"]
    for vid in s.get("voice_msgs", []):
        try: await bot.delete_message(chat, vid)
        except: pass
    s["voice_msgs"] = []

    cur   = s["current"]
    total = len(s["questions"])
    test  = s["questions"][cur]
    (q,a,b,c,d,correct,expl,qtype,is_latex,img_url,audio,lang,tl) = test
    q_s = render_text(q)
    a_s = render_text(str(a or ""))
    b_s = render_text(str(b or ""))
    c_s = render_text(str(c or ""))
    d_s = render_text(str(d or ""))
    try: tl = int(tl) if tl and int(tl) > 0 else 0
    except: tl = 0

    photo = await _photo_for(test, user_id)

    # Yuqori xabar: faqat statistika (natija yo'q)
    await _edit_board(s, _board_text(s))
    await asyncio.sleep(0.3)  # Telegram rate limit uchun

    # Yozma savol
    if qtype == "write_answer":
        user_state[user_id] = "text_answer"
        tmr = f"⏱ {tl}s" if tl > 0 else "∞"
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔊", callback_data="speak_question"),
             InlineKeyboardButton(text=tmr,  callback_data="noop_timer"),
             InlineKeyboardButton(text="🛑 Stop", callback_data="test_stop")],
            HOME_BTN,
        ])
        q_text = f"✍️ Savol {cur+1}/{total}\n\n{q_s}\n\n📝 Javobingizni yozing:"
        await _edit_question(s, q_text, kb, photo)
        if tl > 0:
            async def write_cd():
                left = tl
                while left > 0:
                    await asyncio.sleep(5); left = max(0, left-5)
                    sx = test_sessions.get(user_id)
                    if not sx or sx.get("answered"): return
                    if left > 0:
                        try:
                            await bot.edit_message_reply_markup(
                                chat_id=sx["board_chat_id"],
                                message_id=sx["q_msg_id"],
                                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                    [InlineKeyboardButton(text="🔊", callback_data="speak_question"),
                                     InlineKeyboardButton(text=f"⏱ {left}s", callback_data="noop_timer"),
                                     InlineKeyboardButton(text="🛑 Stop", callback_data="test_stop")],
                                    HOME_BTN,
                                ])
                            )
                        except: pass
                sx = test_sessions.get(user_id)
                if not sx or sx.get("answered"): return
                sx["answered"] = True; sx["wrong"] += 1
                sx["timer_task"] = None
                user_state[user_id] = None
                await _advance(user_id)
            s["timer_task"] = asyncio.create_task(write_cd())
        return

    user_state[user_id] = "in_test"
    kb     = _build_kb(a_s, b_s, c_s, d_s, tl)
    q_text = f"🧪 Savol {cur+1}/{total}\n\n{q_s}"
    await _edit_question(s, q_text, kb, photo)

    if tl <= 0: return
    async def cd():
        left = tl
        while left > 0:
            await asyncio.sleep(5); left = max(0, left-5)
            sx = test_sessions.get(user_id)
            if not sx or sx.get("answered"): return
            if left > 0:
                try:
                    await bot.edit_message_reply_markup(
                        chat_id=sx["board_chat_id"],
                        message_id=sx["q_msg_id"],
                        reply_markup=_build_kb(a_s, b_s, c_s, d_s, left)
                    )
                except: pass
        sx = test_sessions.get(user_id)
        if not sx or sx.get("answered"): return
        sx["answered"] = True
        sx["wrong"]   += 1
        sx["timer_task"] = None  # avval tozala — _show_result chaqirmasdan
        # To'g'ridan-to'g'ri natija ko'rsat va keyingisiga o't
        try:
            await _edit_board(sx, _board_text(sx, "⏱ Vaqt tugadi!"))
        except Exception:
            pass
        await asyncio.sleep(2.0)
        if test_sessions.get(user_id):
            await _advance(user_id)
    s["timer_task"] = asyncio.create_task(cd())

# ── natijani ko'rsatish ──
async def _show_result(user_id, message, result_text):
    s = test_sessions.get(user_id)
    if not s: return
    s["answered"] = True
    if s.get("timer_task"):
        try: s["timer_task"].cancel()
        except: pass
        s["timer_task"] = None

    cur   = s["current"]
    total = len(s["questions"])
    test  = s["questions"][cur]
    q_s   = render_text(test[0])

    # Yuqori: statistika + natija
    await _edit_board(s, _board_text(s, result_text))

    # Natija paytida rasm olib tashlanadi — faqat matn qoladi
    q_text = f"🧪 Savol {cur+1}/{total}\n\n{q_s}"
    await _edit_question(s, q_text, None, None)  # photo=None

    await asyncio.sleep(3.0)
    # Sleep paytida session o'chib ketmadimi tekshirish
    if not test_sessions.get(user_id):
        return
    await _advance(user_id)

async def _advance(user_id):
    s = test_sessions.get(user_id)
    if not s: return
    s["current"] += 1
    if s["current"] >= len(s["questions"]):
        await finish_test(user_id)
    else:
        await show_question(user_id)

# ── javob tekshirish ──
async def check_button_answer(user_id, answer, message):
    s = test_sessions.get(user_id)
    if not s or s.get("answered"): return
    if s.get("timer_task"):
        try: s["timer_task"].cancel()
        except: pass
        s["timer_task"] = None
    test = s["questions"][s["current"]]
    a,b,c,d   = test[1],test[2],test[3],test[4]
    correct   = str(test[5] or "").strip()
    expl      = render_text(str(test[6] or ""))
    sel_map   = {"A":str(a),"B":str(b),"C":str(c),"D":str(d)}
    lab_map   = {k: render_text(str(v or "")) for k,v in sel_map.items()}
    selected  = sel_map.get(answer.upper(),"")
    if correct.upper() in ("A","B","C","D"):
        is_ok = answer.upper() == correct.upper()
        correct_key = correct.upper()
    else:
        is_ok = render_text(selected).strip().lower() == render_text(correct).strip().lower()
        # to'g'ri kalit — qaysi javob to'g'ri ekanini topamiz
        correct_key = None
        for k,v in lab_map.items():
            if v.strip().lower() == render_text(correct).strip().lower():
                correct_key = k; break

    # ── Tugmalarni natija bilan yangilaymiz ──
    rows = []
    for k, cb, spk in [("A","ans_A","speak_a"),("B","ans_B","speak_b"),
                        ("C","ans_C","speak_c"),("D","ans_D","speak_d")]:
        label = lab_map[k]
        if k == answer.upper():
            icon = "✅" if is_ok else "❌"
            show_label = f"{icon} {label}"
            rows.append([InlineKeyboardButton(text=show_label, callback_data="noop_result")])
        elif not is_ok and k == correct_key:
            show_label = f"🟢 {label}"
            rows.append([InlineKeyboardButton(text=show_label, callback_data="noop_result")])
        else:
            if len(label) <= 22:
                rows.append([
                    InlineKeyboardButton(text="🔊",  callback_data=spk),
                    InlineKeyboardButton(text=label, callback_data="noop_result"),
                ])
            else:
                rows.append([InlineKeyboardButton(text=label, callback_data="noop_result")])
    rows.append(HOME_BTN)
    result_kb = InlineKeyboardMarkup(inline_keyboard=rows)

    # Keyboard ni darhol yangilaymiz (foydalanuvchi ko'zi shu yerda)
    try:
        await bot.edit_message_reply_markup(
            chat_id=s["board_chat_id"],
            message_id=s["q_msg_id"],
            reply_markup=result_kb
        )
    except Exception:
        pass

    if is_ok:
        s["correct"] += 1
        result = "✅ To'g'ri!"
        if expl: result += f"\n\n💡 {expl}"
    else:
        s["wrong"] += 1
        correct_show = lab_map.get(correct_key, render_text(correct)) if correct_key else render_text(correct)
        result = f"❌ Xato!\n\n✅ To'g'ri javob:\n{correct_show}"
        if expl: result += f"\n\n💡 Izoh: {expl}"
    await _show_result(user_id, message, result)

async def check_text_answer(user_id, user_answer, message):
    s = test_sessions.get(user_id)
    if not s or s.get("answered"): return
    if s.get("timer_task"):
        try: s["timer_task"].cancel()
        except: pass
        s["timer_task"] = None
    test    = s["questions"][s["current"]]
    correct = render_text(str(test[5] or "")).strip().lower()
    expl    = render_text(str(test[6] or ""))
    if str(user_answer).strip().lower() == correct:
        s["correct"] += 1; result = "✅ To'g'ri!"
    else:
        s["wrong"] += 1; result = f"❌ Xato!\n✅ To'g'ri: {render_text(str(test[5]))}"
    if expl: result += f"\n\n💡 {expl}"
    user_state[user_id] = None
    await _show_result(user_id, message, result)

# ── test tugash ──
async def next_question(user_id, message=None): await _advance(user_id)

async def finish_test(user_id, message=None):
    s = test_sessions.get(user_id)
    if not s: return
    if s.get("timer_task"):
        try: s["timer_task"].cancel()
        except: pass
    user_state[user_id] = None
    ok, err = s["correct"], s["wrong"]
    total   = ok + err
    pct     = round(ok*100/total,1) if total else 0
    emoji   = "🏆" if pct>=80 else "👍" if pct>=60 else "💪"
    result_kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🏠 Bosh menyuga qaytish", callback_data="go_home_dashboard")
    ]])
    await _edit_board(s,
        f"{emoji} Test yakunlandi!\n\n"
        f"✅ To'g'ri:   {ok}\n❌ Noto'g'ri: {err}\n📊 Natija: {pct}%"
    )
    # Pastki xabar — keyboard bilan yakuniy ko'rinish
    chat = s["board_chat_id"]
    qmid = s.get("q_msg_id")
    if qmid:
        try: await bot.edit_message_text(
            text="🎯 Test yakunlandi!", chat_id=chat,
            message_id=qmid, reply_markup=result_kb
        )
        except:
            try: await bot.send_message(chat, "🎯 Test yakunlandi!", reply_markup=result_kb)
            except: pass
    test_sessions.pop(user_id, None)

async def stop_test(user_id, message): await finish_test(user_id, message)

# ── TTS ──
async def speak_text(user_id, message, text):
    s = test_sessions.get(user_id)
    lang = "uz"
    if s:
        try: lang = str(s["questions"][s["current"]][11]).lower()
        except: pass
    try:
        conn = psycopg2.connect(DATABASE_URL); cur = conn.cursor()
        cur.execute("SELECT gender FROM users WHERE user_id=%s",(user_id,))
        row = cur.fetchone(); cur.close(); conn.close()
        gender = row[0] if row else ""
    except: gender = ""
    voices = {
        "uz":"uz-UZ-MadinaNeural" if "Ayol" in str(gender) else "uz-UZ-SardorNeural",
        "en":"en-US-GuyNeural","ru":"ru-RU-DmitryNeural",
    }
    import re as _re
    from pydub import AudioSegment as _AS
    _pts = _re.split(r'\[en\](.*?)\[/en\]', str(text), flags=_re.DOTALL)
    _segs = []
    for _i,_p in enumerate(_pts):
        _cl = tts_clean(_p) if _i%2==0 else _p.strip()
        _cl = _re.sub(r'\s+',' ',_cl).strip()
        if not _cl or not any(_c.isalnum() for _c in _cl): continue
        _segs.append((_cl, voices["en"] if _i%2==1 else voices.get(lang,voices["uz"])))
    if not _segs: return
    _comb = _AS.silent(duration=0)
    for _st,_sv in _segs:
        _tmp = f"tts_tmp_{user_id}_{abs(hash(_st))}.mp3"
        try:
            await edge_tts.Communicate(text=_st,voice=_sv).save(_tmp)
            if os.path.exists(_tmp) and os.path.getsize(_tmp)>0:
                _comb += _AS.from_mp3(_tmp)
        except: pass
        finally:
            try: os.remove(_tmp)
            except: pass
    if len(_comb)==0: return
    fname = f"tts_{user_id}.mp3"
    try:
        _comb.export(fname,format="mp3")
        vm = await message.answer_voice(FSInputFile(fname))
        sx = test_sessions.get(user_id)
        if sx: sx.setdefault("voice_msgs",[]).append(vm.message_id)
    except: pass
    finally:
        try: os.remove(fname)
        except: pass

async def speak_question(u,m):
    s=test_sessions.get(u)
    if s: await speak_text(u,m,s["questions"][s["current"]][0])
async def speak_a(u,m):
    s=test_sessions.get(u)
    if s: await speak_text(u,m,s["questions"][s["current"]][1])
async def speak_b(u,m):
    s=test_sessions.get(u)
    if s: await speak_text(u,m,s["questions"][s["current"]][2])
async def speak_c(u,m):
    s=test_sessions.get(u)
    if s: await speak_text(u,m,s["questions"][s["current"]][3])
async def speak_d(u,m):
    s=test_sessions.get(u)
    if s: await speak_text(u,m,s["questions"][s["current"]][4])

def latex_to_image(latex_text, filename):
    try:
        import matplotlib.pyplot as plt
        fig = plt.figure(figsize=(6,2))
        plt.text(0.05,0.5,f"${latex_text}$",fontsize=24)
        plt.axis("off")
        plt.savefig(filename,bbox_inches="tight",dpi=150)
        plt.close(fig)
    except: pass
