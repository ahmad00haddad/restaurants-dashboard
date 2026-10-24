"""Priority-1 group from جهات_لم_تُرسل_لها_بعد.md, added to the Nas Irbid tab. Nothing is written or sent: the personal sentences
are honest and general because nothing more is known about these sponsors yet. Run once: python nas_group1.py"""
import sys
sys.path.insert(0, ".")

BIZ = "لأنكم من الشركات اللي بيعرفها أهل إربد، والسلسلة كلها عن ناس المدينة وحكاياتهم."
FIT = "وهاي محتوى محلي نظيف وقريب من الناس."
CH = ("لأنك عضو مجلس إدارة غرفة صناعة إربد، وصنّاع المدينة جزء من ذاكرتها.", "وبنحب نوصل لصنّاع إربد القدامى بحلقة تحكي حكايتهم.")
G = [  # name, kind, category, greeting, ask, hook, fit, note, score, tier
    ("بنك الاتحاد", "brand", "بنك", "السادة بنك الاتحاد", "season", BIZ, FIT, "CSR: رعاية حلقة أو موسم. ابحث عن بريد المسؤول العلني", 55, "B"),
    ("بنك الصفوة", "brand", "بنك", "السادة بنك الصفوة", "season", BIZ, FIT, "CSR. ابحث عن بريد المسؤول العلني", 50, "B"),
    ("أمنية", "brand", "اتصالات", "السادة أمنية", "episode", "لأن خدماتكم بتوصل لبيوت إربد وناسها.", "وسلسلتنا محتوى محلي نظيف بيوصل لنفس الناس.", "تسويق رقمي/CSR", 50, "B"),
    ("طلبات الأردن", "brand", "تقنية وتوصيل", "السادة طلبات", "episode", "لأن خدمتكم بتوصل لبيوت إربد، والأكل جزء كبير من حكاياتها.", "وعندنا حلقات عن الأكل والمخابز متل سركيس الخبّاز.", "حلقات الطعام «طعم التراث»، قسم التسويق", 50, "B"),
    ("لومينوس", "org", "شركة", "السادة لومينوس", "episode", "لأنكم معروفين بدعم المواهب والصناعات الإبداعية.", "وسلسلتنا عمل إبداعي مستقل من إربد.", "دعم المواهب الريادية والصناعات الإبداعية", 50, "B"),
    ("جو بترول", "brand", "محروقات", "السادة جو بترول", "episode", "لأنكم شركة وطنية بتخدم أهل إربد وغيرها.", FIT, "تواصل مؤسسي، ابحث عن بريد علني", 45, "C"),
    ("مأمون حلاوة", "other", "نائب رئيس غرفة صناعة إربد", "الأستاذ مأمون حلاوة", "episode", CH[0], CH[1], "عبر غرفة صناعة إربد", 60, "B"),
    ("هاني شطناوي", "other", "عضو مجلس إدارة غرفة صناعة إربد", "الأستاذ هاني شطناوي", "episode", CH[0], CH[1], "عبر غرفة صناعة إربد. المصدر 2021، تحقق من عضويته", 55, "B"),
    ("مأمون الخضر", "other", "عضو مجلس إدارة غرفة صناعة إربد", "الأستاذ مأمون الخضر", "episode", CH[0], CH[1], "عبر غرفة صناعة إربد", 55, "B"),
    ("د. نضال الحاسي", "other", "أمين سر غرفة صناعة إربد", "الدكتور نضال الحاسي", "episode", "لأنك أمين سر غرفة صناعة إربد، وصنّاع المدينة جزء من ذاكرتها.", CH[1], "عبر غرفة صناعة إربد. صلته بشركة العرب للأدوية غير مؤكدة", 55, "B"),
]
if __name__ == "__main__":
    import agent
    rows = []
    for name, kind, cat, greet, ask, hook, fit, note, score, tier in G:
        who = f"{cat}، {name}"
        rows.append({"program": "nas", "kind": kind, "name": name, "category": cat, "city": "إربد" if kind == "other" else None, "score": score,
                     "source": "جهات_لم_تُرسل_لها_بعد.md (أولوية 1)", "notes": note, "status": "new",
                     "profile": {"summary": who, "tier": tier, "lang": "ar", "channel": "email", "analysed_by": "nas-seed",
                                 "nas": {"who": who, "love": "", "episode": "", "ask": ask, "greeting": greet, "hook": hook, "fit": fit}}})
    r = agent.db.req("POST", "leads", body=rows, prefer="return=representation,resolution=ignore-duplicates")
    print("added", len(r or []))
