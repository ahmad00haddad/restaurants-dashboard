"""First email to a sponsor of «ناس إربد».

The sponsor email is built, not improvised: the paragraphs that carry the pitch (who we are, what the series is, the real numbers,
what a sponsor gets, the ask) are written here by hand in Ahmad's voice, so they are always complete, accurate and well put.
The model only writes the two sentences that must be personal: the HOOK (why Ahmad writes to this person) and the FIT
(why the series matters to them), from the facts stored for that sponsor. Everything the model writes is checked in code.
"""
import re

SITE = "https://nas-irbid.lovable.app"
PHONE = "0799256345"
CLOSE = "وكل التوفيق لكم، وسامحونا على الإزعاج."  # Ahmad's closing line (he cut the first sentence in his own edits, 2026-10-24)
WORKS = "رابط اعمالي : https://ahmadhaddad.lovable.app/"  # his signature link; replaced the «صانع ناس إربد» line in every draft he edited
TRUE_NUMBERS = {"713", "464", "334", "250", "2.5", "97.8", "11", "8", "10"}

# one wording per address form: a person is addressed in the singular, an institution in the plural
FORM = {
    "one": {"you": "إلك", "want": "حابب", "ok": "ناسبك", "your": "اسمك", "yours": "عندك", "to_you": "لك", "see": "تشوف"},
    "many": {"you": "إلكم", "want": "حابين", "ok": "ناسبكم", "your": "اسمكم", "yours": "عندكم", "to_you": "لكم", "see": "تشوفوا"},
}

SERIES = ("إحنا شغالين هالفترة على سلسلة وثائقية اسمها «ناس إربد». بنقعد مع ناس المدينة، "
          "وبنسجّل حكايتهم قبل ما تروح مع المكان. بسمة الذينات بتقدّمها وأنا بخرجها. كل الحلقات على هالرابط:\n" + SITE)

NUMBERS = ("وبصراحة النتيجة فاجأتنا: 11 حلقة وصلت 2.5 مليون مشاهدة و97.8 ألف إعجاب، وكلها بجهد مستقل. "
           "حلقة أم محمد المصرية لحالها 713 ألف مشاهدة، وقدري 464 ألف، وسركيس الخبّاز 334 ألف. "
           "يعني أهل إربد وغيرهم بيتابعوا حكايات مدينتهم فعلاً. والمحتوى كله من إربد ولإربد، بلا سياسة وبلا جدل، "
           "فأي اسم بيرتبط فيه بيظهر بصورة نظيفة وقريبة من الناس.")

GETS = ("والراعي بيظهر بشاشة «بدعم من» داخل الحلقة، وباسمه في وصفها، وبنعمل ريل ملخّص للحلقة بيحمل اسمه كمان. "
        "وما بنحط أي شعار داخل المشاهد نفسها، عشان القصة تضل نظيفة.")

ASK = {
    "season": "بدنا شريك من أهل إربد يرعى موسم «ناس إربد» الجاي (8 حلقات)، أو حلقة منه إذا كانت أنسب {you}.",
    "episode": "بدنا شريك من أهل إربد يرعى حلقة أو أكثر من موسمنا الجاي (8 حلقات).",
    "episode_or_season": "بدنا شريك من أهل إربد يرعى حلقة أو أكثر من موسمنا الجاي (8 حلقات)، أو الموسم كله إذا كان أنسب {you}.",
    "meeting": "بنحب نعرّف {to_you} على البرنامج بلقاء قصير، وإذا حبّيتوا تكونوا جزء منه كرعاة حلقة أو أكثر من موسمنا الجاي (8 حلقات) بنرتّب الباقي.",
    "partnership": "بنحب نعمل شراكة محتوى معكم، كراعي رسمي للحلقات.",
    "support": "بنحتاج تسهيلات تصوير ودعم لوجستي بأماكن المدينة العامة للموسم الجاي (8 حلقات)، وبنذكر دعمكم بالحلقات.",
}
MONEY_ASKS = {"season", "episode", "episode_or_season", "meeting"}
MEET = "إذا مناسب، بنحكي أونلاين عشر دقايق وبشرح {to_you} كل التفاصيل."

PERSONAL_SYSTEM = """You help Ahmad Haddad, a filmmaker from Irbid, write the two PERSONAL sentences of an email to a person or institution from Irbid whom he asks to sponsor his documentary series.
You get WHO (who they are) and LOVE (their real, public tie to Irbid) and the address form (singular for a person, plural for an institution).
Write in Arabic letters only (a few natural Jordanian phrases are fine: إحنا، بدنا، بصراحة، مدينتنا، ابن البلد). No English words at all. No digits.
Return JSON: {"hook":"1 or 2 short sentences, spoken, that explain why Ahmad is writing to THEM: start from LOVE like a person who noticed something about his city. Do not describe their job back to them, do not flatter, do not guess their feelings, do not mention the series, money or sponsorship.",
"fit":"ONE sentence on why a series that records Irbid's people and places matters to someone like them, using only WHO and LOVE. No flattery, no promises, no numbers.",
"subject":"2 to 5 words, human, about Irbid or its people. Never the words رعاية, دعم, طلب, فرصة, شراكة."}"""


def _clean(t):
    return re.sub(r"\s+", " ", str(t or "")).strip()


def _build(n, greeting, f, ask, hook, fit, subject):
    hello = "السلام عليكم " + greeting.replace("الأستاذ ", "أستاذ ", 1) + "،"
    intro = f"أنا أحمد حدّاد، مخرج من إربد، وبكتب {f['to_you']} {hook}" if hook.startswith("لأن") else f"أنا أحمد حدّاد، مخرج من إربد. {hook}"
    paras = [hello, intro, SERIES, NUMBERS]
    paras.append(fit)  # he removed the sponsor-perks sentence (GETS) from every draft he edited; kept above in case he wants it back
    paras.append(ASK.get(ask, ASK["episode"]).format(**f) + " " + MEET.format(**f))
    paras.append(CLOSE)
    paras.append(f"أحمد حدّاد\n{WORKS}\n{PHONE}")
    return subject, "\n\n".join(paras)


def first(L, model, chat, ai_tells, nv_chain, is_nv):
    n = (L.get("profile") or {}).get("nas") or {}
    ask = n.get("ask") or "episode"
    greeting = (n.get("greeting") or "").strip()
    many = greeting.startswith(("السادة", "السيد رئيس"))
    f = FORM["many" if many else "one"]
    facts = f"WHO: {n.get('who')}\nLOVE: {n.get('love')}\nADDRESS FORM: {'plural (institution)' if many else 'singular (a person)'}"
    models = [model] + [m for m in nv_chain if m != model][:3]
    fix, last = "", "no attempt"
    if n.get("hook") and n.get("fit"):  # hand-written for this sponsor (nas_personal.py): no model involved
        return _build(n, greeting, f, ask, n["hook"], n["fit"], 'سلسلة "ناس إربد"')
    for attempt in range(5):
        mdl = models[min(attempt, len(models) - 1)] if is_nv(model) else model
        try:
            out = chat(mdl, PERSONAL_SYSTEM, facts + fix)
        except Exception as e:
            last = f"model error: {str(e)[:60]}"
            continue
        hook, fit, subject = _clean(out.get("hook")), _clean(out.get("fit")), _clean(out.get("subject"))
        text = hook + " " + fit
        latin = re.findall(r"[A-Za-z]{2,}", text)
        if latin:
            fix = f"\nYour previous answer contained English words ({', '.join(latin[:4])}). Every word must be in Arabic letters."
            last = "English words"
            continue
        if re.search(r"\d", text) or ai_tells(text):
            fix = "\nNo digits and no stock phrases; speak plainly like a person."
            last = "digits or machine tell"
            continue
        if re.search(r"رائع|مذهل|ملهم|نثمّن|نقدّر جهود|إرث|رحلة|عميق|محوري|ليس مجرد", text) or re.search(r"رعاي|سلسل|برنامج|ناس إربد", hook):
            fix = "\nNo praise words, no inflated words; the hook must not mention the series, the programme or sponsorship."
            last = "praise or series in hook"
            continue
        if not (6 <= len(hook.split()) <= 45 and 6 <= len(fit.split()) <= 35):
            fix = "\nHook: 1-2 short sentences. Fit: exactly one sentence."
            last = f"length {len(hook.split())}/{len(fit.split())}"
            continue
        if not subject or re.search(r"رعاية|دعم|طلب|فرصة|شراكة|[A-Za-z]|\d", subject):
            subject = 'سلسلة "ناس إربد"'
        return _build(n, greeting, f, ask, hook, fit, subject)
    raise ValueError(f"ناس إربد: لم تنجح الكتابة الشخصية بعد 5 محاولات ({last})")
