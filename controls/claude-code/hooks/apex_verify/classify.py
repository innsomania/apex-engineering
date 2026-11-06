"""Prompt classification for turn locking."""

import re

FOLD = str.maketrans("ıİşŞğĞüÜöÖçÇâÂîÎ", "iissgguuoocCaAiI")

# Explicit stop requests may include context; do not mistake a task mentioning a stop control for one.
STOP_COMMANDS = re.compile(r"\b(dur|durdur|stop|yeter|bekle|pause|wait)\b")
STOP_PHRASE = re.compile(
    r"\b(do not continue|don't continue|do not proceed|don't proceed|pause here|wait here|"
    r"(?:bu |the )?(?:işi|isi|work|iş|is) (?:hemen )?(?:durdur|stop|pause)|"
    r"(?:artık|artik) devam etme|stop (?:now|here|please)|"
    r"please stop working(?: on this task)?|lütfen artik bekle|lutfen artik bekle)\b"
)
STOP_ANYWHERE = re.compile(r"\b(ne yapiyorsun|ne yapiyosun|kafayi yi\w*)\b")

# Abuse stops the agent, but abuse inside a question ("neden boyle, orospu cocugu?") is a complaint
# demanding the fix, so it must not lock edits.
ABUSE = re.compile(
    r"\b(salak|aptal|gerizekali|orospu|siktir|sikim|amk|aq|allah belani|allahin belasi|"
    r"kafayi mi yedin)\b"
)
QUESTION_START = re.compile(r"\W*(neden|niye|nasil|nerede|nereye|hangi|kim|why|how|what|where|which)\b")

# "neden calismiyor?" reports something broken: the user wants it fixed, not just explained.
FAILURE_REPORT = re.compile(
    r"\b(calismiyor|calismadi|bozuk\w*|bozul\w*|hata\w*|olmuyor|acilmiyor|yuklenmiyor|gelmiyor|"
    r"broken|error|errors|fail|fails|failed|failing|crash\w*|not working|doesn.?t work)\b"
)
QUESTION_ANYWHERE = re.compile(r"\b(neden|niye|nasil|why|how)\b")
QUESTION_PARTICLES = re.compile(r"\b(m[iu]|m[iu]s[iu]n(?:[iu]z)?|m[iu]y[iu]m|midir|mudur|miydi|muydu)\b")

# "düzeltir misin?", "can you add tests?": requests phrased as questions.
POLITE_REQUEST = re.compile(r"\w[aeiu]r m[iu]s[iu]n\b|\b(can|could|would|will) you\b|\blutfen\b|\bplease\b")

# "devam etsene, neden durdun?": a go-ahead wrapped in a question is still a go-ahead.
# The -sene/-sana urging form is matched only on known verb stems, so "kasana" or "bu sene" stay plain words.
GO_AHEAD = re.compile(
    r"\bdevam\b|\b(go on|carry on|keep going|continue)\b|"
    r"\b(et|yap|bak|gel|git|yaz|ekle|sil|bitir|baslat|basla|calistir|duzelt|gonder|pushla|kur|bas)"
    r"s[ae]n[ae]\b"
)

# "tamam mi ?" on its own asks how authorized work is going; it must not halt that work.
STATUS_CHECK = re.compile(
    r"\W*(tamam m[iu]|oldu mu|bitti mi|ne durumda|durum ne|is it done|are you done|done yet|status)\W*"
)
STATUS_NOTE = ("The user asked for a status. Give it in one sentence, then continue any work they already "
               "authorized; do not start new work.")

# A question no longer locks edits: a complaint phrased as a question ("kontrol et dedim, mal misin?")
# still wants the work, and only the model sees the whole conversation.
QUESTION_NOTE = ("The user's message reads like a question. If it asks something, answer it directly in your "
                 "first sentence. If it repeats or presses an earlier request, do that work now. Do not start "
                 "new work the user has not asked for.")

LOCK_REASONS = {
    "stop": "The user wants you to stop. Do not continue or restart the previous work. In at most two "
            "sentences say what state the work is in, then wait for the user's instruction.",
}


def classify(prompt: str) -> str | None:
    """'stop', 'question', 'status' or None for a user message; a stop signal outranks a question."""
    text = prompt.translate(FOLD).lower()
    task_context = bool(re.search(r"\b(fix|add|write|test|explain|rename|hook|button|control|hata|duzelt)\b", text))
    explicit_stop = bool(STOP_ANYWHERE.search(text) or (STOP_PHRASE.search(text) and not task_context))
    if not explicit_stop and STOP_COMMANDS.search(text):
        asks = bool(text.rstrip().endswith("?") or QUESTION_PARTICLES.search(text))
        explicit_stop = not asks and not task_context and bool(
            re.search(r"\b(stop|pause|wait|dur|durdur|bekle|yeter)\b.{0,50}"
            r"\b(now|here|please|artık|artik|lutfen|lütfen|işi|isi|work|doing|devam|continue)\b", text)
            or len(text.split()) <= 3)
    if explicit_stop:
        return "stop"
    if STATUS_CHECK.fullmatch(text):
        return "status"
    asks = bool(QUESTION_START.match(text) or text.rstrip().endswith("?")
                or QUESTION_PARTICLES.search(text))
    # A go-ahead wins even inside abuse or a question ("essek misin? yapsana"), and abuse alone is
    # frustration with the work, not a stop: only an explicit stop command halts.
    if GO_AHEAD.search(text) or ABUSE.search(text) or (asks and FAILURE_REPORT.search(text)):
        return None
    if QUESTION_START.match(text):
        return "question"
    if POLITE_REQUEST.search(text):
        return None
    if asks:
        return "question"
    return None
