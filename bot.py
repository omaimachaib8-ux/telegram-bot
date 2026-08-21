import os
import sqlite3
import threading
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import telebot
from telebot import types
from gtts import gTTS


# =========================================================
# إعداد البوت
# =========================================================

TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    raise ValueError("BOT_TOKEN غير موجود في GitHub Secrets")

bot = telebot.TeleBot(TOKEN)

TIMEZONE = ZoneInfo("Africa/Algiers")
DB_NAME = "bot_data.db"


# =========================================================
# قاعدة البيانات
# =========================================================

def db():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS students (
            user_id INTEGER PRIMARY KEY,
            branch TEXT,
            unit_index INTEGER DEFAULT 0,
            lesson_index INTEGER DEFAULT 0,
            level INTEGER DEFAULT 1,
            weekly_lessons INTEGER DEFAULT 0,
            reminder_time TEXT,
            reminder_enabled INTEGER DEFAULT 0,
            last_reminder_date TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            test_type TEXT,
            unit INTEGER,
            lesson INTEGER,
            score INTEGER,
            total INTEGER,
            level INTEGER,
            created_at TEXT
        )
    """)

    conn.commit()
    conn.close()


def ensure_student(user_id):
    conn = db()

    conn.execute("""
        INSERT OR IGNORE INTO students
        (user_id, unit_index, lesson_index, level,
         weekly_lessons, reminder_enabled)
        VALUES (?, 0, 0, 1, 0, 0)
    """, (user_id,))

    conn.commit()
    conn.close()


def student(user_id):
    ensure_student(user_id)

    conn = db()

    row = conn.execute(
        "SELECT * FROM students WHERE user_id = ?",
        (user_id,)
    ).fetchone()

    conn.close()

    return row


def update_student(user_id, **values):
    if not values:
        return

    conn = db()

    parts = []
    data = []

    allowed = {
        "branch",
        "unit_index",
        "lesson_index",
        "level",
        "weekly_lessons",
        "reminder_time",
        "reminder_enabled",
        "last_reminder_date"
    }

    for key, value in values.items():

        if key not in allowed:
            continue

        parts.append(f"{key} = ?")
        data.append(value)

    if not parts:
        conn.close()
        return

    data.append(user_id)

    conn.execute(
        f"""
        UPDATE students
        SET {", ".join(parts)}
        WHERE user_id = ?
        """,
        data
    )

    conn.commit()
    conn.close()


def save_result(
    user_id,
    test_type,
    unit,
    lesson,
    score,
    total,
    level
):

    conn = db()

    conn.execute("""
        INSERT INTO results
        (user_id, test_type, unit, lesson,
         score, total, level, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        user_id,
        test_type,
        unit,
        lesson,
        score,
        total,
        level,
        datetime.now(TIMEZONE).isoformat()
    ))

    conn.commit()
    conn.close()


# =========================================================
# الشعب
# =========================================================

BRANCHES = {

    "math": {
        "name": "📐 رياضيات",
        "group": "scientific"
    },

    "science": {
        "name": "🧪 علوم تجريبية",
        "group": "scientific"
    },

    "technical": {
        "name": "⚙️ تقني رياضي",
        "group": "scientific"
    },

    "management": {
        "name": "📊 تسيير واقتصاد",
        "group": "scientific"
    },

    "literature": {
        "name": "📚 آداب وفلسفة",
        "group": "literary"
    },

    "languages": {
        "name": "🌍 لغات أجنبية",
        "group": "literary"
    }
}


# =========================================================
# الوحدات الرسمية
# =========================================================

UNITS = {

    1: {
        "title": "Exploring the Past",
        "theme": "Ancient Civilizations",
        "group": "literary"
    },

    2: {
        "title": "Ill-Gotten Gains Never Prosper",
        "theme": "Ethics in Business",
        "group": "both"
    },

    3: {
        "title": "Schools: Different and Alike",
        "theme": "Education in the World",
        "group": "literary"
    },

    4: {
        "title": "Safety First",
        "theme": "Advertising, Consumers and Safety",
        "group": "scientific"
    },

    5: {
        "title": "It's a Giant Leap for Mankind",
        "theme": "Astronomy and the Solar System",
        "group": "scientific"
    },

    6: {
        "title": "We Are a Family",
        "theme": "Feelings and Emotions",
        "group": "both"
    }
}


BRANCH_UNITS = {

    "scientific": [2, 4, 5, 6],

    "literary": [1, 2, 3, 6]
}


# =========================================================
# محتوى الدروس
#
# كل وحدة = 6 دروس
# الدروس تفتح تلقائيا بالتدرج
# لا يختار التلميذ اليوم يدويا
# =========================================================

LESSONS = {

# =========================================================
# UNIT 1
# =========================================================

1: [

{
"title": "Lesson 1 — Ancient Civilizations",

"words": [
("civilization", "حضارة",
 "Ancient Egypt was a great civilization."),

("ancient", "قديم",
 "The Egyptians built ancient monuments."),

("empire", "إمبراطورية",
 "The Roman Empire was powerful."),

("heritage", "تراث",
 "The pyramids are part of Egyptian heritage."),

("achievement", "إنجاز",
 "Building the pyramids was a great achievement.")
],

"grammar": "Past Simple / Past Perfect",

"paragraph":
"Ancient civilizations developed great societies. "
"They built monuments and created important systems."
},

{
"title": "Lesson 2 — Contributions",

"words": [
("contribution", "مساهمة",
 "The civilization made an important contribution."),

("invention", "اختراع",
 "Writing was an important invention."),

("develop", "يطور",
 "Ancient people developed new techniques."),

("culture", "ثقافة",
 "Every civilization has its own culture."),

("agriculture", "زراعة",
 "Agriculture helped people settle.")
],

"grammar": "Past Perfect",

"paragraph":
"Ancient civilizations made important contributions "
"to human development."
},

{
"title": "Lesson 3 — Life in the Past",

"words": [
("monument", "معلم / نصب",
 "The monument attracts visitors."),

("rule", "يحكم",
 "The king ruled the empire."),

("protect", "يحمي",
 "People protected their cities."),

("survive", "ينجو",
 "People learned to survive."),

("settle", "يستقر",
 "People settled near rivers.")
],

"grammar": "Used to / Had to / Was able to",

"paragraph":
"People used to live in small communities. "
"They had to work together to survive."
},

{
"title": "Lesson 4 — Historical Change",

"words": [
("expand", "يتوسع",
 "The empire expanded rapidly."),

("collapse", "ينهار",
 "The empire eventually collapsed."),

("influence", "يؤثر",
 "Ancient cultures influenced modern societies."),

("discover", "يكتشف",
 "Scientists discovered historical objects."),

("preserve", "يحافظ على",
 "Museums preserve historical objects.")
],

"grammar": "Linking Words",

"paragraph":
"Ancient civilizations influenced the modern world. "
"However, some civilizations eventually collapsed."
},

{
"title": "Lesson 5 — Civilization and Heritage",

"words": [
("society", "مجتمع",
 "Ancient societies developed different systems."),

("custom", "عادة",
 "Every society has its customs."),

("tradition", "تقليد",
 "Traditions can survive for centuries."),

("historical", "تاريخي",
 "The city has many historical sites."),

("archaeologist", "عالم آثار",
 "The archaeologist studied the remains.")
],

"grammar": "Relative Clauses",

"paragraph":
"Archaeologists study ancient societies to understand "
"their traditions and achievements."
},

{
"title": "Lesson 6 — Unit Review",

"words": [
("civilization", "حضارة",
 "Civilizations leave important achievements."),

("heritage", "تراث",
 "We should protect our heritage."),

("contribution", "مساهمة",
 "Their contribution was important."),

("influence", "تأثير",
 "Their influence remains today."),

("achievement", "إنجاز",
 "The project was an achievement.")
],

"grammar": "Grammar Review",

"paragraph":
"Ancient civilizations left a strong influence on humanity."
}

],


# =========================================================
# UNIT 2
# =========================================================

2: [

{
"title": "Lesson 1 — Ethics in Business",

"words": [
("corruption", "فساد",
 "Corruption damages society."),

("bribery", "رشوة",
 "Bribery is illegal."),

("fraud", "احتيال",
 "Fraud can harm consumers."),

("illegal", "غير قانوني",
 "Illegal activities must be stopped."),

("ethics", "أخلاقيات",
 "Business ethics are important.")
],

"grammar": "Present Simple / Passive Voice",

"paragraph":
"Ethics are essential in business. "
"Corruption and fraud can damage society."
},

{
"title": "Lesson 2 — Fighting Fraud",

"words": [
("counterfeit", "مقلد / مزور",
 "Counterfeit products can be dangerous."),

("forge", "يزور",
 "Criminals may forge documents."),

("smuggle", "يهرب",
 "Some criminals smuggle illegal goods."),

("steal", "يسرق",
 "Stealing is a crime."),

("crime", "جريمة",
 "Financial crime affects society.")
],

"grammar": "Passive Voice",

"paragraph":
"Financial crimes must be fought by governments "
"and responsible citizens."
},

{
"title": "Lesson 3 — Social Responsibility",

"words": [
("responsibility", "مسؤولية",
 "Companies have social responsibilities."),

("honesty", "أمانة",
 "Honesty builds trust."),

("trust", "ثقة",
 "Customers need to trust businesses."),

("fair", "عادل",
 "Businesses should offer fair prices."),

("consumer", "مستهلك",
 "Consumers have rights.")
],

"grammar": "Modals: must / should / have to",

"paragraph":
"Responsible companies respect consumers and "
"follow ethical rules."
},

{
"title": "Lesson 4 — Money and Crime",

"words": [
("tax", "ضريبة",
 "Citizens pay taxes."),

("money laundering", "غسل الأموال",
 "Money laundering is a serious crime."),

("investigation", "تحقيق",
 "The police started an investigation."),

("evidence", "دليل",
 "The investigators found evidence."),

("punishment", "عقوبة",
 "Crime may lead to punishment.")
],

"grammar": "Cause and Effect",

"paragraph":
"Financial crimes can have serious consequences."
},

{
"title": "Lesson 5 — Ethical Business",

"words": [
("honest", "صادق",
 "An honest company gains trust."),

("transparent", "شفاف",
 "Transparent companies provide information."),

("lawful", "قانوني",
 "Businesses must be lawful."),

("quality", "جودة",
 "Consumers expect good quality."),

("protect", "يحمي",
 "Laws protect consumers.")
],

"grammar": "Conditionals",

"paragraph":
"If companies behave ethically, consumers will trust them."
},

{
"title": "Lesson 6 — Unit Review",

"words": [
("corruption", "فساد",
 "Corruption harms society."),

("bribery", "رشوة",
 "Bribery is illegal."),

("fraud", "احتيال",
 "Fraud harms consumers."),

("ethics", "أخلاقيات",
 "Ethics guide responsible businesses."),

("consumer", "مستهلك",
 "Consumers have rights.")
],

"grammar": "Unit Grammar Review",

"paragraph":
"Ethical business practices help create a fairer society."
}

],


# =========================================================
# UNIT 3
# =========================================================

3: [

{
"title": "Lesson 1 — Education Around the World",

"words": [
("education", "تعليم",
 "Education is important for development."),

("schooling", "تمدرس",
 "Schooling prepares children for life."),

("curriculum", "منهاج",
 "The curriculum includes many subjects."),

("student", "تلميذ",
 "Every student needs support."),

("teacher", "أستاذ",
 "A teacher helps students learn.")
],

"grammar": "Comparatives and Superlatives",

"paragraph":
"Education systems differ from one country to another."
},

{
"title": "Lesson 2 — Comparing Systems",

"words": [
("system", "نظام",
 "Each country has its own education system."),

("public", "عمومي",
 "Public schools are accessible to many students."),

("private", "خاص",
 "Some families choose private schools."),

("compulsory", "إجباري",
 "Education is compulsory in many countries."),

("primary", "ابتدائي",
 "Children start primary education early.")
],

"grammar": "Comparing and Contrasting",

"paragraph":
"Some education systems are similar while others "
"are quite different."
},

{
"title": "Lesson 3 — School Life",

"words": [
("secondary", "ثانوي",
 "Secondary education prepares students for higher studies."),

("university", "جامعة",
 "Many students continue at university."),

("exam", "اختبار",
 "Students prepare carefully for exams."),

("qualification", "مؤهل",
 "Qualifications can help students find jobs."),

("subject", "مادة",
 "English is an important subject.")
],

"grammar": "Relative Clauses",

"paragraph":
"School life gives students knowledge and skills."
},

{
"title": "Lesson 4 — Education and Development",

"words": [
("literacy", "محو الأمية",
 "Literacy improves people's lives."),

("knowledge", "معرفة",
 "Education provides knowledge."),

("skill", "مهارة",
 "Students develop useful skills."),

("development", "تنمية",
 "Education supports development."),

("opportunity", "فرصة",
 "Education creates opportunities.")
],

"grammar": "Cause and Effect",

"paragraph":
"Education contributes to social and economic development."
},

{
"title": "Lesson 5 — Improving Education",

"words": [
("access", "وصول",
 "Everyone should have access to education."),

("equality", "مساواة",
 "Equality is important in education."),

("reform", "إصلاح",
 "Education reform can improve schools."),

("method", "طريقة",
 "Teachers use different methods."),

("achievement", "إنجاز",
 "Students celebrate their achievements.")
],

"grammar": "Modals and Advice",

"paragraph":
"Governments should improve education and provide equal opportunities."
},

{
"title": "Lesson 6 — Unit Review",

"words": [
("education", "تعليم",
 "Education is essential."),

("curriculum", "منهاج",
 "The curriculum contains different subjects."),

("qualification", "مؤهل",
 "Qualifications are useful."),

("equality", "مساواة",
 "Equality should be respected."),

("opportunity", "فرصة",
 "Education creates opportunities.")
],

"grammar": "Unit Grammar Review",

"paragraph":
"Good education systems help societies develop."
}

],


# =========================================================
# UNIT 4
# =========================================================

4: [

{
"title": "Lesson 1 — Advertising",

"words": [
("advertisement", "إعلان",
 "The advertisement attracted many customers."),

("consumer", "مستهلك",
 "Consumers need reliable information."),

("product", "منتج",
 "The product was advertised online."),

("brand", "علامة تجارية",
 "The company created a popular brand."),

("commercial", "إشهار تجاري",
 "The commercial appeared on television.")
],

"grammar": "Passive Voice",

"paragraph":
"Advertising influences consumers and helps companies "
"promote their products."
},

{
"title": "Lesson 2 — Consumer Rights",

"words": [
("right", "حق",
 "Consumers have important rights."),

("protection", "حماية",
 "Consumer protection is necessary."),

("guarantee", "ضمان",
 "The product comes with a guarantee."),

("complaint", "شكوى",
 "The customer made a complaint."),

("refund", "استرجاع المال",
 "The shop offered a refund.")
],

"grammar": "Modal Verbs",

"paragraph":
"Consumers should know their rights and responsibilities."
},

{
"title": "Lesson 3 — Food Safety",

"words": [
("organic", "عضوي",
 "Some people prefer organic food."),

("processed", "مصنّع",
 "Processed food should be consumed carefully."),

("ingredient", "مكوّن",
 "The ingredients are listed on the package."),

("healthy", "صحي",
 "A balanced diet is healthy."),

("additive", "مادة مضافة",
 "Some foods contain additives.")
],

"grammar": "Quantifiers",

"paragraph":
"Consumers should read food labels before buying products."
},

{
"title": "Lesson 4 — Genetically Modified Food",

"words": [
("genetically modified", "معدل وراثيا",
 "Some foods are genetically modified."),

("gene", "جين",
 "Genes determine many biological characteristics."),

("scientist", "عالم",
 "Scientists study food technology."),

("benefit", "فائدة",
 "The technology may have benefits."),

("risk", "خطر",
 "Consumers should understand possible risks.")
],

"grammar": "Expressing Opinion",

"paragraph":
"People have different opinions about genetically modified food."
},

{
"title": "Lesson 5 — Fast Food",

"words": [
("fast food", "وجبات سريعة",
 "Fast food is popular among young people."),

("obesity", "سمنة",
 "Too much unhealthy food may contribute to obesity."),

("diet", "نظام غذائي",
 "A balanced diet is important."),

("nutrition", "تغذية",
 "Good nutrition supports health."),

("harmful", "ضار",
 "Too much sugar can be harmful.")
],

"grammar": "Cause and Effect",

"paragraph":
"A healthy lifestyle requires balanced food choices."
},

{
"title": "Lesson 6 — Unit Review",

"words": [
("advertising", "إشهار",
 "Advertising affects consumers."),

("consumer", "مستهلك",
 "Consumers have rights."),

("protection", "حماية",
 "Consumer protection is important."),

("organic", "عضوي",
 "Organic food is popular."),

("nutrition", "تغذية",
 "Good nutrition is essential.")
],

"grammar": "Unit Grammar Review",

"paragraph":
"Responsible consumers think carefully before buying products."
}

],


# =========================================================
# UNIT 5
# =========================================================

5: [

{
"title": "Lesson 1 — The Solar System",

"words": [
("planet", "كوكب",
 "Earth is a planet."),

("solar system", "النظام الشمسي",
 "The solar system contains many objects."),

("orbit", "مدار",
 "The Earth orbits the Sun."),

("star", "نجم",
 "The Sun is a star."),

("galaxy", "مجرة",
 "Our galaxy is called the Milky Way.")
],

"grammar": "Present Simple / Scientific Facts",

"paragraph":
"The solar system contains the Sun, planets and other objects."
},

{
"title": "Lesson 2 — Space Exploration",

"words": [
("spacecraft", "مركبة فضائية",
 "The spacecraft travelled through space."),

("astronaut", "رائد فضاء",
 "The astronaut entered the spacecraft."),

("mission", "مهمة",
 "The mission was successful."),

("explore", "يستكشف",
 "Scientists explore space."),

("launch", "يطلق",
 "The rocket was launched successfully.")
],

"grammar": "Past Simple / Passive",

"paragraph":
"Space missions have helped scientists understand the universe."
},

{
"title": "Lesson 3 — The Moon",

"words": [
("moon", "قمر",
 "The Moon orbits Earth."),

("surface", "سطح",
 "The lunar surface is rocky."),

("crater", "فوهة",
 "The Moon has many craters."),

("gravity", "جاذبية",
 "Gravity affects objects."),

("lunar", "قمري",
 "Scientists study lunar rocks.")
],

"grammar": "Scientific Comparisons",

"paragraph":
"The Moon is smaller than Earth and has much weaker gravity."
},

{
"title": "Lesson 4 — Discoveries",

"words": [
("discovery", "اكتشاف",
 "The discovery changed science."),

("scientist", "عالم",
 "The scientist studied the planet."),

("research", "بحث",
 "Space research requires advanced technology."),

("technology", "تكنولوجيا",
 "Technology helps scientists explore space."),

("evidence", "دليل",
 "Scientists need evidence.")
],

"grammar": "Present Perfect",

"paragraph":
"Scientific discoveries have changed our understanding of space."
},

{
"title": "Lesson 5 — A Giant Leap",

"words": [
("achievement", "إنجاز",
 "Landing on the Moon was a great achievement."),

("challenge", "تحد",
 "Space exploration presents many challenges."),

("innovation", "ابتكار",
 "Innovation improves space technology."),

("future", "مستقبل",
 "Future missions may explore distant planets."),

("universe", "كون",
 "The universe is enormous.")
],

"grammar": "Future Forms",

"paragraph":
"Future space missions may reveal new information about the universe."
},

{
"title": "Lesson 6 — Unit Review",

"words": [
("planet", "كوكب",
 "Earth is our planet."),

("astronaut", "رائد فضاء",
 "The astronaut completed the mission."),

("spacecraft", "مركبة فضائية",
 "The spacecraft travelled far."),

("discovery", "اكتشاف",
 "The discovery was important."),

("universe", "كون",
 "The universe contains billions of stars.")
],

"grammar": "Unit Grammar Review",

"paragraph":
"Space exploration has expanded human knowledge."
}

],


# =========================================================
# UNIT 6
# =========================================================

6: [

{
"title": "Lesson 1 — Feelings",

"words": [
("happy", "سعيد",
 "She felt happy."),

("sad", "حزين",
 "He was sad."),

("angry", "غاضب",
 "The child was angry."),

("proud", "فخور",
 "Her parents were proud."),

("worried", "قلق",
 "He was worried.")
],

"grammar": "Adjectives and Feelings",

"paragraph":
"People experience different feelings in their daily lives."
},

{
"title": "Lesson 2 — Family Relationships",

"words": [
("relationship", "علاقة",
 "Good relationships require respect."),

("relative", "قريب",
 "She visited her relatives."),

("support", "دعم",
 "Families support each other."),

("respect", "احترام",
 "Respect is important in families."),

("trust", "ثقة",
 "Trust strengthens relationships.")
],

"grammar": "Each Other / One Another",

"paragraph":
"Family relationships become stronger when people support each other."
},

{
"title": "Lesson 3 — Communication",

"words": [
("communicate", "يتواصل",
 "People communicate in different ways."),

("conversation", "محادثة",
 "They had a long conversation."),

("opinion", "رأي",
 "Everyone can express an opinion."),

("disagreement", "خلاف",
 "They had a disagreement."),

("understand", "يفهم",
 "Good communication helps people understand each other.")
],

"grammar": "Reported Speech",

"paragraph":
"Good communication helps people solve disagreements peacefully."
},

{
"title": "Lesson 4 — Helping Others",

"words": [
("kindness", "لطف",
 "Kindness makes people feel valued."),

("helpful", "متعاون",
 "She is always helpful."),

("generous", "كريم",
 "He is generous with his time."),

("care", "اهتمام",
 "Families care about each other."),

("compassion", "تعاطف",
 "Compassion is an important human quality.")
],

"grammar": "Giving Advice",

"paragraph":
"Kindness and compassion help create strong human relationships."
},

{
"title": "Lesson 5 — Social Life",

"words": [
("friendship", "صداقة",
 "Friendship is based on trust."),

("community", "مجتمع",
 "People live in communities."),

("cooperation", "تعاون",
 "Cooperation helps groups succeed."),

("conflict", "نزاع",
 "People should solve conflicts peacefully."),

("harmony", "انسجام",
 "Respect can create harmony.")
],

"grammar": "Conditionals",

"paragraph":
"If people communicate respectfully, they can solve conflicts."
},

{
"title": "Lesson 6 — Unit Review",

"words": [
("feeling", "شعور",
 "Everyone has feelings."),

("relationship", "علاقة",
 "Relationships require respect."),

("communication", "تواصل",
 "Communication is essential."),

("friendship", "صداقة",
 "Friendship requires trust."),

("cooperation", "تعاون",
 "Cooperation brings people together.")
],

"grammar": "Unit Grammar Review",

"paragraph":
"Healthy relationships depend on respect, trust and communication."
}

]
}


# =========================================================
# أسئلة الاختبارات
#
# مستوى 1 = أساسي
# مستوى 2 = متوسط
# مستوى 3 = متقدم
# =========================================================

def build_questions(unit, lesson, level):

    content = LESSONS[unit][lesson]

    words = content["words"]

    questions = []

    # السؤال 1
    word, meaning, sentence = words[0]

    if level == 1:

        questions.append((
            f"What does '{word}' mean?",
            [
                meaning,
                words[1][1],
                words[2][1],
                words[3][1],
                words[4][1]
            ],
            meaning
        ))

    elif level == 2:

        questions.append((
            f"Choose the word that best completes the sentence:\n"
            f"{sentence}",
            [
                word,
                words[1][0],
                words[2][0],
                words[3][0],
                words[4][0]
            ],
            word
        ))

    else:

        questions.append((
            f"Which option is closest in meaning to '{word}'?",
            [
                meaning,
                words[1][1],
                words[2][1],
                words[3][1],
                "None of the above"
            ],
            meaning
        ))

    # السؤال 2
    word2, meaning2, sentence2 = words[1]

    questions.append((
        f"Choose the correct word:\n{sentence2}",
        [
            word2,
            words[0][0],
            words[2][0],
            words[3][0],
            words[4][0]
        ],
        word2
    ))

    # السؤال 3
    grammar = content["grammar"]

    grammar_questions = [

        (
            "Which tense is commonly used for completed actions in the past?",
            [
                "Past Simple",
                "Present Simple",
                "Future Simple",
                "Present Continuous",
                "Past Continuous"
            ],
            "Past Simple"
        ),

        (
            "Which expression is used to talk about a past habit?",
            [
                "used to",
                "is used to",
                "will",
                "has to",
                "is going to"
            ],
            "used to"
        ),

        (
            "Which word introduces a contrast?",
            [
                "However",
                "Therefore",
                "Moreover",
                "Finally",
                "Because"
            ],
            "However"
        ),

        (
            "Which structure can express obligation?",
            [
                "must",
                "might",
                "could",
                "would",
                "may"
            ],
            "must"
        ),

        (
            "Which form is commonly used for scientific facts?",
            [
                "Present Simple",
                "Past Perfect",
                "Future Perfect",
                "Past Continuous",
                "Conditional Perfect"
            ],
            "Present Simple"
        )
    ]

    questions.append(
        grammar_questions[
            (unit + lesson + level) % len(grammar_questions)
        ]
    )

    # السؤال 4
    word4, meaning4, sentence4 = words[3]

    questions.append((
        f"Which sentence uses '{word4}' correctly?",
        [
            sentence4,
            f"The word {word4} is never used in English.",
            f"They {word4} yesterdayly.",
            f"{word4} are a country.",
            "None of the above"
        ],
        sentence4
    ))

    # السؤال 5
    word5, meaning5, sentence5 = words[4]

    questions.append((
        "Choose the correct meaning:",
        [
            meaning5,
            words[0][1],
            words[1][1],
            words[2][1],
            words[3][1]
        ],
        meaning5
    ))

    # مستوى 3 سؤال إضافي أكثر تحديا
    if level >= 3:

        questions.append((
            "Which sentence best expresses the main idea of the lesson?",
            [
                content["paragraph"],
                "The topic has no connection with society.",
                "The lesson only concerns grammar.",
                "The vocabulary is unrelated to the topic.",
                "None of these."
            ],
            content["paragraph"]
        ))

    return questions


# =========================================================
# الاختبار النهائي للوحدة
# =========================================================

def build_final_test(unit, level):

    lessons = LESSONS[unit]

    questions = []

    for i, lesson in enumerate(lessons[:5]):

        word, meaning, sentence = lesson["words"][0]

        options = [
            meaning,
            lesson["words"][1][1],
            lesson["words"][2][1],
            lesson["words"][3][1],
            "None of the above"
        ]

        questions.append((
            f"Which meaning best matches '{word}'?",
            options,
            meaning
        ))

    # سؤال إضافي حسب المستوى
    if level >= 2:

        questions.append((
            "Which statement best describes the purpose of the unit?",
            [
                lessons[0]["paragraph"],
                "The unit only teaches isolated vocabulary.",
                "The unit has no connection with real life.",
                "The unit is unrelated to communication.",
                "None of the above"
            ],
            lessons[0]["paragraph"]
        ))

    return questions


# =========================================================
# حالة الاستماع
# =========================================================

waiting_for_audio = set()


# =========================================================
# حالة الاختبارات
# =========================================================

test_sessions = {}


# =========================================================
# القوائم
# =========================================================

def main_menu():

    keyboard = types.InlineKeyboardMarkup()

    keyboard.add(
        types.InlineKeyboardButton(
            "🎓 الدراسة",
            callback_data="study"
        )
    )

    keyboard.add(
        types.InlineKeyboardButton(
            "📚 برنامجي",
            callback_data="program"
        )
    )

    keyboard.add(
        types.InlineKeyboardButton(
            "🔊 الاستماع",
            callback_data="listen"
        )
    )

    keyboard.add(
        types.InlineKeyboardButton(
            "🔔 التذكير",
            callback_data="reminder"
        )
    )

    keyboard.add(
        types.InlineKeyboardButton(
            "📊 تقدمي",
            callback_data="progress"
        )
    )

    return keyboard


def branch_menu():

    keyboard = types.InlineKeyboardMarkup()

    for key, data in BRANCHES.items():

        keyboard.add(
            types.InlineKeyboardButton(
                data["name"],
                callback_data=f"branch_{key}"
            )
        )

    return keyboard


def user_units(user_id):

    s = student(user_id)

    if not s["branch"]:
        return []

    group = BRANCHES[s["branch"]]["group"]

    return BRANCH_UNITS[group]


def unit_menu(user_id):

    keyboard = types.InlineKeyboardMarkup()

    for unit in user_units(user_id):

        info = UNITS[unit]

        keyboard.add(
            types.InlineKeyboardButton(
                f"📘 Unit {unit} — {info['title']}",
                callback_data=f"openunit_{unit}"
            )
        )

    return keyboard


def lesson_actions(unit, lesson):

    keyboard = types.InlineKeyboardMarkup()

    keyboard.add(
        types.InlineKeyboardButton(
            "📝 اختبار الدرس",
            callback_data=f"lesson_test_{unit}_{lesson}"
        )
    )

    keyboard.add(
        types.InlineKeyboardButton(
            "🔊 الاستماع",
            callback_data="listen"
        )
    )

    keyboard.add(
        types.InlineKeyboardButton(
            "📚 برنامجي",
            callback_data="program"
        )
    )

    return keyboard


# =========================================================
# START
# =========================================================

@bot.message_handler(commands=["start"])
def start(message):

    user_id = message.from_user.id

    ensure_student(user_id)

    s = student(user_id)

    if not s["branch"]:

        bot.send_message(
            message.chat.id,
            "🇬🇧 أهلاً بك في English 3AS Bot!\n\n"
            "قبل أن نبدأ، اختر شعبتك:",
            reply_markup=branch_menu()
        )

        return

    bot.send_message(
        message.chat.id,
        "🇬🇧 أهلاً بك مجددًا!\n\n"
        "اختر ما تريد:",
        reply_markup=main_menu()
    )


# =========================================================
# بدء الدراسة تلقائيا
# =========================================================

def start_next_lesson(chat_id, user_id):

    s = student(user_id)

    units = user_units(user_id)

    if not units:
        return

    unit_index = s["unit_index"]

    if unit_index >= len(units):

        bot.send_message(
            chat_id,
            "🏆 لقد أتممت جميع وحدات برنامج شعبتك!\n\n"
            "أحسنت، يمكنك مراجعة النتائج من زر 📊 تقدمي.",
            reply_markup=main_menu()
        )

        return

    unit = units[unit_index]

    lesson_index = s["lesson_index"]

    if lesson_index >= len(LESSONS[unit]):

        update_student(
            user_id,
            unit_index=unit_index + 1,
            lesson_index=0,
            weekly_lessons=s["weekly_lessons"]
        )

        start_next_lesson(chat_id, user_id)

        return

    send_lesson(
        chat_id,
        user_id,
        unit,
        lesson_index
    )


# =========================================================
# إرسال الدرس
# =========================================================

def send_lesson(
    chat_id,
    user_id,
    unit,
    lesson_index
):

    content = LESSONS[unit][lesson_index]

    level = student(user_id)["level"]

    info = UNITS[unit]

    text = (
        f"📘 Unit {unit}\n"
        f"{info['title']}\n"
        f"🎯 {info['theme']}\n\n"
        f"📖 {content['title']}\n\n"
        f"📈 مستواك الحالي: {level}\n\n"
        "📝 المصطلحات:\n\n"
    )

    for number, item in enumerate(
        content["words"],
        1
    ):

        word, meaning, sentence = item

        text += (
            f"{number}. {word}\n"
            f"➡️ {meaning}\n"
            f"💬 {sentence}\n\n"
        )

    text += (
        f"🔤 Grammar:\n"
        f"{content['grammar']}\n\n"
        "✍️ Model Paragraph:\n"
        f"{content['paragraph']}\n\n"
        "خذ وقتك في فهم الدرس، ثم اضغط على اختبار الدرس."
    )

    bot.send_message(
        chat_id,
        text,
        reply_markup=lesson_actions(
            unit,
            lesson_index
        )
    )


# =========================================================
# إنهاء الدرس والانتقال للدرس التالي
# =========================================================

def complete_lesson(
    chat_id,
    user_id
):

    s = student(user_id)

    units = user_units(user_id)

    unit_index = s["unit_index"]
    lesson_index = s["lesson_index"]

    if unit_index >= len(units):
        return

    unit = units[unit_index]

    new_lesson = lesson_index + 1
    weekly = s["weekly_lessons"] + 1

    # مراجعة أسبوعية بعد 5 دروس
    if weekly >= 5:

        update_student(
            user_id,
            lesson_index=new_lesson,
            weekly_lessons=0
        )

        bot.send_message(
            chat_id,
            "📚 أحسنت!\n\n"
            "لقد أكملت مجموعة هذا الأسبوع.\n"
            "قبل مواصلة الدروس، حان وقت المراجعة الأسبوعية 🔄"
        )

        send_weekly_review(
            chat_id,
            user_id,
            unit
        )

        return

    # نهاية الوحدة
    if new_lesson >= len(LESSONS[unit]):

        update_student(
            user_id,
            unit_index=unit_index,
            lesson_index=new_lesson,
            weekly_lessons=weekly
        )

        bot.send_message(
            chat_id,
            "🎉 أكملت دروس هذه الوحدة!\n\n"
            "🏆 حان الآن وقت الاختبار النهائي للوحدة."
        )

        send_final_test(
            chat_id,
            user_id,
            unit
        )

        return

    update_student(
        user_id,
        lesson_index=new_lesson,
        weekly_lessons=weekly
    )

    bot.send_message(
        chat_id,
        "✅ تم إكمال الدرس!\n\n"
        "📖 سننتقل الآن تدريجيًا إلى الدرس التالي."
    )

    start_next_lesson(
        chat_id,
        user_id
    )


# =========================================================
# المراجعة الأسبوعية
# =========================================================

def send_weekly_review(
    chat_id,
    user_id,
    unit
):

    level = student(user_id)["level"]

    questions = build_final_test(
        unit,
        level
    )

    send_test(
        chat_id,
        user_id,
        questions,
        "weekly",
        unit
    )


# =========================================================
# الاختبار النهائي
# =========================================================

def send_final_test(
    chat_id,
    user_id,
    unit
):

    level = student(user_id)["level"]

    questions = build_final_test(
        unit,
        level
    )

    send_test(
        chat_id,
        user_id,
        questions,
        "final",
        unit
    )


# =========================================================
# نظام الاختبارات
# =========================================================

def send_test(
    chat_id,
    user_id,
    questions,
    test_type,
    number
):

    test_sessions[user_id] = {

        "questions": questions,

        "index": 0,

        "score": 0,

        "type": test_type,

        "number": number
    }

    send_question(
        chat_id,
        user_id
    )


def send_question(
    chat_id,
    user_id
):

    session = test_sessions.get(user_id)

    if not session:
        return

    questions = session["questions"]

    index = session["index"]

    if index >= len(questions):

        finish_test(
            chat_id,
            user_id
        )

        return

    question, options, correct = questions[index]

    keyboard = types.InlineKeyboardMarkup()

    for number, option in enumerate(
        options,
        1
    ):

        keyboard.add(
            types.InlineKeyboardButton(
                f"{number}️⃣ {option}",
                callback_data=f"answer|{number}"
            )
        )

    bot.send_message(
        chat_id,
        f"🧠 السؤال {index + 1}/{len(questions)}\n\n"
        f"{question}",
        reply_markup=keyboard
    )


def finish_test(
    chat_id,
    user_id
):

    session = test_sessions.get(user_id)

    if not session:
        return

    score = session["score"]

    total = len(session["questions"])

    test_type = session["type"]

    number = session["number"]

    s = student(user_id)

    level = s["level"]

    save_result(
        user_id,
        test_type,
        number,
        s["lesson_index"],
        score,
        total,
        level
    )

    percentage = (
        score / total
    ) * 100

    # =====================================================
    # تعديل المستوى
    # =====================================================

    old_level = level

    if percentage >= 85 and level < 3:

        level += 1

    elif percentage < 50 and level > 1:

        level -= 1

    update_student(
        user_id,
        level=level
    )

    # =====================================================
    # رسالة النتيجة
    # =====================================================

    if percentage >= 85:

        message = (
            "🌟 ممتاز جدًا!\n"
            "لقد أظهرت تقدمًا واضحًا."
        )

    elif percentage >= 70:

        message = (
            "👏 جيد جدًا!\n"
            "استمر بهذا المستوى."
        )

    elif percentage >= 50:

        message = (
            "👍 نتيجة جيدة.\n"
            "هناك بعض النقاط التي تحتاج إلى مراجعة."
        )

    else:

        message = (
            "🌱 لا بأس.\n"
            "المراجعة والمحاولة مرة أخرى جزء من التعلم."
        )

    level_message = ""

    if level > old_level:

        level_message = (
            "\n\n⬆️ ارتفع مستواك!\n"
            f"المستوى الجديد: {level}"
        )

    elif level < old_level:

        level_message = (
            "\n\n🔄 سنراجع بعض النقاط أكثر.\n"
            f"المستوى الحالي: {level}"
        )

    else:

        level_message = (
            f"\n\n📈 المستوى الحالي: {level}"
        )

    if test_type == "final":

        title = "🏆 الاختبار النهائي للوحدة"

    elif test_type == "weekly":

        title = "🔄 المراجعة الأسبوعية"

    else:

        title = "📝 اختبار الدرس"

    bot.send_message(
        chat_id,
        f"{title}\n\n"
        f"📊 النتيجة: {score}/{total}\n"
        f"📈 النسبة: {percentage:.0f}%\n\n"
        f"{message}"
        f"{level_message}"
    )

    del test_sessions[user_id]

    # اختبار الدرس فقط يفتح الدرس التالي
    if test_type == "lesson":

        complete_lesson(
            chat_id,
            user_id
        )

    elif test_type == "final":

        s = student(user_id)

        units = user_units(user_id)

        current_index = s["unit_index"]

        next_index = current_index + 1

        if next_index < len(units):

            update_student(
                user_id,
                unit_index=next_index,
                lesson_index=0
            )

            bot.send_message(
                chat_id,
                "🎉 رائع!\n\n"
                "تم إنهاء الوحدة.\n"
                "سنبدأ الوحدة التالية تدريجيًا."
            )

            start_next_lesson(
                chat_id,
                user_id
            )

        else:

            bot.send_message(
                chat_id,
                "🏆 لقد أكملت برنامج شعبتك بالكامل!\n\n"
                "يمكنك الاستمرار في المراجعة والاختبارات."
            )

    elif test_type == "weekly":

        bot.send_message(
            chat_id,
            "🔄 انتهت المراجعة الأسبوعية.\n\n"
            "سنواصل البرنامج تدريجيًا.",
            reply_markup=main_menu()
        )


# =========================================================
# إنشاء الصوت
# =========================================================

def send_audio(
    chat_id,
    text
):

    filename = (
        f"audio_{chat_id}_"
        f"{int(time.time())}.mp3"
    )

    try:

        tts = gTTS(
            text=text,
            lang="en",
            slow=False
        )

        tts.save(filename)

        with open(
            filename,
            "rb"
        ) as audio:

            bot.send_audio(
                chat_id,
                audio,
                caption="🔊 استمع جيدًا وحاول تكرار النطق."
            )

    except Exception as error:

        print(
            "Audio error:",
            error
        )

        bot.send_message(
            chat_id,
            "❌ حدث خطأ أثناء إنشاء التسجيل الصوتي."
        )

    finally:

        if os.path.exists(filename):

            os.remove(filename)


# =========================================================
# استقبال النص
# =========================================================

@bot.message_handler(
    content_types=["text"]
)
def text_handler(message):

    user_id = message.from_user.id

    ensure_student(user_id)

    if user_id in waiting_for_audio:

        text = message.text.strip()

        if not text:

            bot.send_message(
                message.chat.id,
                "❌ اكتب نصًا أولًا."
            )

            return

        if len(text) > 3000:

            bot.send_message(
                message.chat.id,
                "⚠️ النص طويل جدًا."
            )

            return

        waiting_for_audio.discard(
            user_id
        )

        bot.send_message(
            message.chat.id,
            "🎧 جارٍ تجهيز التسجيل..."
        )

        send_audio(
            message.chat.id,
            text
        )

        bot.send_message(
            message.chat.id,
            "🔊 يمكنك اختيار نص آخر.",
            reply_markup=main_menu()
        )

        return

    bot.send_message(
        message.chat.id,
        "استخدم الأزرار الموجودة في القائمة.",
        reply_markup=main_menu()
    )


# =========================================================
# معالجة الأزرار
# =========================================================

@bot.callback_query_handler(
    func=lambda call:
    call.data.startswith("answer|")
)
def answer_handler(call):

    user_id = call.from_user.id

    session = test_sessions.get(
        user_id
    )

    if not session:

        bot.answer_callback_query(
            call.id,
            "انتهى الاختبار."
        )

        return

    number = int(
        call.data.split("|")[1]
    )

    index = session["index"]

    question, options, correct = (
        session["questions"][index]
    )

    if number < 1 or number > len(options):

        bot.answer_callback_query(
            call.id,
            "إجابة غير صالحة."
        )

        return

    selected = options[number - 1]

    if selected == correct:

        session["score"] += 1

        bot.answer_callback_query(
            call.id,
            "✅ صحيح!"
        )

    else:

        bot.answer_callback_query(
            call.id,
            "❌ غير صحيح."
        )

        bot.send_message(
            call.message.chat.id,
            f"❌ الإجابة غير صحيحة.\n\n"
            f"✅ الإجابة الصحيحة:\n{correct}"
        )

    session["index"] += 1

    send_question(
        call.message.chat.id,
        user_id
    )


@bot.callback_query_handler(
    func=lambda call: True
)
def callback_handler(call):

    user_id = call.from_user.id

    ensure_student(user_id)

    data = call.data

    # =====================================================
    # الدراسة
    # =====================================================

    if data == "study":

        s = student(user_id)

        if not s["branch"]:

            bot.send_message(
                call.message.chat.id,
                "اختر شعبتك أولًا:",
                reply_markup=branch_menu()
            )

            bot.answer_callback_query(call.id)

            return

        start_next_lesson(
            call.message.chat.id,
            user_id
        )

        bot.answer_callback_query(call.id)

        return

    # =====================================================
    # اختيار الشعبة
    # =====================================================

    if data == "branch":

        bot.send_message(
            call.message.chat.id,
            "🎓 اختر شعبتك:",
            reply_markup=branch_menu()
        )

        bot.answer_callback_query(call.id)

        return

    if data.startswith("branch_"):

        branch = data.replace(
            "branch_",
            ""
        )

        if branch not in BRANCHES:

            bot.answer_callback_query(
                call.id
            )

            return

        update_student(
            user_id,
            branch=branch,
            unit_index=0,
            lesson_index=0,
            level=1,
            weekly_lessons=0
        )

        group = BRANCHES[branch]["group"]

        names = [
            UNITS[u]["title"]
            for u in BRANCH_UNITS[group]
        ]

        text = (
            f"✅ تم اختيار شعبتك:\n"
            f"{BRANCHES[branch]['name']}\n\n"
            "📚 الوحدات التي ستدرسها:\n\n"
        )

        for i, name in enumerate(
            names,
            1
        ):

            text += (
                f"{i}. {name}\n"
            )

        text += (
            "\n🎯 لن تختار الأيام يدويًا.\n"
            "سيبدأ البرنامج من الدرس الأول "
            "ثم ينتقل بك تدريجيًا حسب تقدمك."
        )

        bot.send_message(
            call.message.chat.id,
            text,
            reply_markup=main_menu()
        )

        bot.answer_callback_query(
            call.id
        )

        return

    # =====================================================
    # البرنامج
    # =====================================================

    if data == "program":

        s = student(user_id)

        if not s["branch"]:

            bot.send_message(
                call.message.chat.id,
                "اختر شعبتك أولًا.",
                reply_markup=branch_menu()
            )

            bot.answer_callback_query(
                call.id
            )

            return

        bot.send_message(
            call.message.chat.id,
            "📚 وحدات برنامج شعبتك:",
            reply_markup=unit_menu(user_id)
        )

        bot.answer_callback_query(
            call.id
        )

        return

    # =====================================================
    # فتح وحدة
    # =====================================================

    if data.startswith("openunit_"):

        unit = int(
            data.replace(
                "openunit_",
                ""
            )
        )

        if unit not in user_units(user_id):

            bot.answer_callback_query(
                call.id,
                "هذه الوحدة ليست ضمن برنامج شعبتك."
            )

            return

        info = UNITS[unit]

        bot.send_message(
            call.message.chat.id,
            f"📘 Unit {unit}\n\n"
            f"📖 {info['title']}\n"
            f"🎯 {info['theme']}\n\n"
            f"📚 عدد الدروس: {len(LESSONS[unit])}\n\n"
            "الدروس تُفتح تدريجيًا حسب تقدمك."
        )

        bot.answer_callback_query(
            call.id
        )

        return

    # =====================================================
    # اختبار الدرس
    # =====================================================

    if data.startswith("lesson_test_"):

        parts = data.split("_")

        unit = int(parts[2])
        lesson = int(parts[3])

        s = student(user_id)

        questions = build_questions(
            unit,
            lesson,
            s["level"]
        )

        send_test(
            call.message.chat.id,
            user_id,
            questions,
            "lesson",
            unit
        )

        bot.answer_callback_query(
            call.id
        )

        return

    # =====================================================
    # الاستماع
    # =====================================================

    if data == "listen":

        waiting_for_audio.add(
            user_id
        )

        keyboard = types.InlineKeyboardMarkup()

        keyboard.add(
            types.InlineKeyboardButton(
                "❌ إلغاء",
                callback_data="cancel_listen"
            )
        )

        bot.send_message(
            call.message.chat.id,
            "🔊 الاستماع\n\n"
            "اكتب الآن ما تريد سماعه بالإنجليزية.\n\n"
            "يمكنك كتابة كلمة أو جملة أو فقرة.",
            reply_markup=keyboard
        )

        bot.answer_callback_query(
            call.id
        )

        return

    # =====================================================
    # إلغاء الاستماع
    # =====================================================

    if data == "cancel_listen":

        waiting_for_audio.discard(
            user_id
        )

        bot.send_message(
            call.message.chat.id,
            "❌ تم إلغاء الاستماع.",
            reply_markup=main_menu()
        )

        bot.answer_callback_query(
            call.id
        )

        return

    # =====================================================
    # التذكير
    # =====================================================

    if data == "reminder":

        keyboard = types.InlineKeyboardMarkup()

        for hour in [17, 18, 19, 20, 21]:

            keyboard.add(
                types.InlineKeyboardButton(
                    f"⏰ {hour:02d}:00",
                    callback_data=f"settime_{hour:02d}:00"
                )
            )

        keyboard.add(
            types.InlineKeyboardButton(
                "❌ إلغاء التذكير",
                callback_data="disable_reminder"
            )
        )

        bot.send_message(
            call.message.chat.id,
            "🔔 اختر وقت التذكير اليومي:",
            reply_markup=keyboard
        )

        bot.answer_callback_query(
            call.id
        )

        return

    if data.startswith("settime_"):

        value = data.replace(
            "settime_",
            ""
        )

        update_student(
            user_id,
            reminder_time=value,
            reminder_enabled=1
        )

        bot.send_message(
            call.message.chat.id,
            f"✅ تم ضبط التذكير على {value} 🇩🇿",
            reply_markup=main_menu()
        )

        bot.answer_callback_query(
            call.id
        )

        return

    if data == "disable_reminder":

        update_student(
            user_id,
            reminder_enabled=0
        )

        bot.send_message(
            call.message.chat.id,
            "🔕 تم إلغاء التذكير.",
            reply_markup=main_menu()
        )

        bot.answer_callback_query(
            call.id
        )

        return

    # =====================================================
    # التقدم
    # =====================================================

    if data == "progress":

        s = student(user_id)

        if not s["branch"]:

            bot.send_message(
                call.message.chat.id,
                "اختر شعبتك أولًا.",
                reply_markup=branch_menu()
            )

            bot.answer_callback_query(
                call.id
            )

            return

        units = user_units(user_id)

        unit_index = min(
            s["unit_index"],
            len(units) - 1
        )

        unit = units[unit_index]

        bot.send_message(
            call.message.chat.id,
            f"📊 تقدمك\n\n"
            f"📚 الوحدة الحالية: {unit}\n"
            f"📖 {UNITS[unit]['title']}\n"
            f"📝 الدرس: {s['lesson_index'] + 1}\n"
            f"🎯 المستوى: {s['level']}/3\n\n"
            f"🔄 دروس هذه الفترة: "
            f"{s['weekly_lessons']}/5"
        )

        bot.answer_callback_query(
            call.id
        )

        return

    bot.answer_callback_query(
        call.id
    )


# =========================================================
# نظام التذكيرات
# =========================================================

def reminder_loop():

    print("🔔 Reminder system started.")

    while True:

        try:

            now = datetime.now(
                TIMEZONE
            )

            current_time = now.strftime(
                "%H:%M"
            )

            today = now.strftime(
                "%Y-%m-%d"
            )

            conn = db()

            students = conn.execute(
                """
                SELECT *
                FROM students
                WHERE reminder_enabled = 1
                AND reminder_time = ?
                AND (
                    last_reminder_date IS NULL
                    OR last_reminder_date != ?
                )
                """,
                (
                    current_time,
                    today
                )
            ).fetchall()

            conn.close()

            for s in students:

                try:

                    bot.send_message(
                        s["user_id"],
                        "🔔 حان وقت الإنجليزية!\n\n"
                        "📚 خصص بعض الوقت لدراسة درس اليوم.",
                        reply_markup=main_menu()
                    )

                    update_student(
                        s["user_id"],
                        last_reminder_date=today
                    )

                except Exception as error:

                    print(
                        "Reminder error:",
                        error
                    )

        except Exception as error:

            print(
                "Reminder loop error:",
                error
            )

        time.sleep(30)


# =========================================================
# التشغيل
# =========================================================

init_db()


reminder_thread = threading.Thread(
    target=reminder_loop,
    daemon=True
)

reminder_thread.start()


print(
    "🇬🇧 English 3AS Bot is running..."
)


bot.infinity_polling(
    timeout=30,
    long_polling_timeout=30
)
