"""Lookalike targeting: each strong past work → the kind of places that would want the same film, and the first email that shows it.

The harvester searches each segment's terms and tags the leads `source = "lookalike:<key>"`; local_ai.write() then sends that work as the
example. No client names in the email (first-contact rule): the similar project is described by its type only.
"""

SEGMENTS = {
    "erasmus_event": {
        "work": "https://www.behance.net/gallery/256801237/Erasmus-event",
        "kind": "org", "cities": ["Irbid", "Amman"],
        "terms": ["university", "youth organization", "conference center", "training center"],
        "ar": ("صوّرتُ مؤخراً فعالية لمشروع شبابي بتمويل أوروبي في الأردن، وهذا الفيديو الذي خرج منها:",
               "إن كان لديكم مؤتمر أو فعالية أو مشروع ممول يحتاج توثيقاً بالفيديو، يسعدني أن نتحدث عنه في لقاء قصير أونلاين."),
        "en": ("I recently filmed an event for an EU-funded youth project in Jordan; this is the video from it:",
               "If you have a conference, event or funded project coming up that needs video coverage, I'd be glad to talk about it in a short online call."),
    },
    "edu_doc": {
        "work": "https://www.behance.net/gallery/256292055/Minecraft-Education-Documentary",
        "kind": "org", "cities": ["Irbid", "Amman"],
        "terms": ["coding academy", "robotics academy", "STEM education center", "educational technology company"],
        "ar": ("صوّرتُ فيلماً وثائقياً قصيراً عن برنامج يعلّم طلاب المدارس عبر الألعاب والتكنولوجيا، وهذا هو:",
               "أظن أن أثر برامجكم يمكن أن يُروى بالطريقة نفسها، من خلال الطلاب والمدربين أنفسهم. يسعدني أن نتحدث عن ذلك في لقاء قصير أونلاين."),
        "en": ("I filmed a short documentary about a programme that teaches school students through games and technology; here it is:",
               "I think the impact of your programmes could be told the same way, through the students and trainers themselves. Happy to talk about it in a short online call."),
    },
    "corporate_event": {
        "work": "https://youtu.be/M_pZnUJC9kg",
        "kind": "org", "cities": ["Irbid", "Amman"],
        "terms": ["software company", "IT company", "business incubator", "coworking space"],
        "ar": ("صوّرتُ مؤخراً فعالية لشركة برمجيات، وهذا الفيديو منها:",
               "إن كان لديكم إطلاق أو فعالية أو مؤتمر قادم، يسعدني أن نتحدث عن تغطيته بالفيديو."),
        "en": ("I recently filmed an event for a software company; this is the video:",
               "If you have a launch, event or conference coming up, I'd be glad to talk about covering it on video."),
    },
    "wedding_hall": {
        "work": "https://youtu.be/_zG1y0YFwGs",
        "kind": "event", "cities": ["Irbid", "Ramtha", "Jerash", "Ajloun", "Mafraq"],
        "terms": ["wedding hall", "event venue", "قاعة أفراح", "صالة أفراح"],
        "ar": ("صوّرتُ فيديو لصالة أفراح في إربد، وهذا هو:",
               "فيديو مثل هذا يعرّف العرسان بالصالة قبل أن يزوروها. يسعدني أن نتحدث عن فيديو لصالتكم."),
        "en": ("I filmed a video for a wedding hall in Irbid; here it is:",
               "A film like this shows couples the hall before they visit. I'd be glad to talk about one for yours."),
    },
    "publisher": {
        "work": "https://www.behance.net/gallery/252096055/_",
        "kind": "brand", "cities": ["Amman", "Irbid"],
        "terms": ["publishing house", "children's books publisher", "دار نشر"],
        "ar": ("صوّرتُ سلسلة فيديوهات لدار نشر كتب أطفال، وهذا مثال منها:",
               "أظن أن كتبكم يمكن أن تصل للأهل والأطفال بالطريقة نفسها. يسعدني أن نتحدث عن ذلك."),
        "en": ("I filmed a video series for a children's book publisher; here is one of them:",
               "I think your books could reach parents and children the same way. Happy to talk about it."),
    },
    "heritage": {
        "work": "https://www.behance.net/gallery/133944345/_",
        "kind": "org", "cities": ["Irbid", "Amman", "Salt", "Jerash", "Madaba", "Karak", "Ajloun"],
        "terms": ["museum", "cultural center", "heritage house", "art gallery"],
        "ar": ("صوّرتُ فيلماً وثائقياً قصيراً عن متحف تراثي في إربد، وهذا هو:",
               "أظن أن ما لديكم يستحق فيلماً مشابهاً يرويه المكان وأهله. يسعدني أن نتحدث عن الفكرة."),
        "en": ("I filmed a short documentary about a heritage museum in Irbid; here it is:",
               "I think your place deserves a similar film, told by the place and its people. Happy to talk about the idea."),
    },
    "fitness": {
        "work": "https://youtu.be/0NHOJqjpdq4",
        "kind": "brand", "cities": ["Irbid", "Amman"],
        "terms": ["gym", "fitness center", "spa", "نادي رياضي"],
        "ar": ("صوّرتُ فيديو لنادٍ رياضي وسبا في إربد، وهذا هو:",
               "يسعدني أن نتحدث عن فيديو يعرّف الناس بناديكم ومدربيكم."),
        "en": ("I filmed a video for a fitness club and spa in Irbid; here it is:",
               "I'd be glad to talk about a film that introduces people to your club and trainers."),
    },
    "optical": {
        "work": "https://youtu.be/HSyGrwAaig0",
        "kind": "brand", "cities": ["Irbid", "Amman"],
        "terms": ["optical store", "optician", "محل نظارات"],
        "ar": ("صوّرتُ إعلاناً لمحل نظارات في إربد، وهذا هو:",
               "يسعدني أن نتحدث عن فيديو مشابه لمحلكم."),
        "en": ("I filmed an ad for an optical store in Irbid; here it is:",
               "Happy to talk about a similar film for your store."),
    },
    "clinic": {
        "work": "https://youtu.be/1XgHSImbRkw",
        "kind": "brand", "cities": ["Irbid"],
        "terms": ["dental clinic", "medical center", "beauty clinic"],
        "ar": ("صوّرتُ فيديو تعريفياً لمركز طبي في إربد، وهذا هو:",
               "يسعدني أن نتحدث عن فيديو يعرّف المراجعين بمركزكم وفريقه."),
        "en": ("I filmed an introduction video for a medical centre in Irbid; here it is:",
               "Happy to talk about a film that introduces patients to your centre and team."),
    },
    "restaurant": {
        "work": "https://www.behance.net/gallery/206884241/Em-Sherif-Cafe-Amman",
        "kind": "restaurant", "cities": ["Irbid", "Amman"],
        "terms": ["fine dining restaurant", "cafe"],
        "ar": ("صوّرنا إعلاناً لمطعم ومقهى في عمّان، وهذا هو:",
               "يسعدني أن نتحدث عن فيديو مشابه لمطعمكم."),
        "en": ("We filmed an ad for a restaurant and café in Amman; here it is:",
               "Happy to talk about a similar film for your restaurant."),
    },
}


def segment(L):
    """The lookalike segment of a lead, or None."""
    src = str(L.get("source") or "")
    return SEGMENTS.get(src.split(":", 1)[1].strip()) if src.startswith("lookalike:") else None
