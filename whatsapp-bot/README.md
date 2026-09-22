# בוט וואטסאפ – פדיקור של אורי

בוט שעונה ללקוחות בוואטסאפ אוטומטית: שעות פתיחה, מחיר, וקביעת תור מלאה
(שם → יום → שעה → אישור). כל תור שנקבע, וכל הודעה שהבוט לא מזהה, נשלחים
כהודעת וואטסאפ אישית לאורי.

**חשוב לדעת מראש:** ה-WhatsApp Business API הרשמי של Meta לא מאפשר לשלוח
הודעות לקבוצת וואטסאפ – רק הודעות אישיות ללקוח או לבעל העסק. לכן הבוט
שולח את כל הסיכומים למספר האישי שלך (`OWNER_PHONE`), לא לקבוצה.

## מה צריך כדי להריץ את זה

1. חשבון מפתחים ב-Meta ואפליקציית WhatsApp Business (חינמי)
2. שרת שרץ 24/7 עם כתובת HTTPS ציבורית (מומלץ: Railway או Render – יש הסבר למטה)

## שלב 1 – הקמת WhatsApp Business API ב-Meta

1. היכנסי ל-[developers.facebook.com](https://developers.facebook.com) והתחברי עם חשבון פייסבוק
2. **My Apps → Create App → סוג "Business"**
3. בתוך האפליקציה, הוסיפי את המוצר **WhatsApp**
4. במסך **WhatsApp → API Setup** תראי:
   - **Temporary access token** – תקף ל-24 שעות, טוב לבדיקות ראשוניות
   - **Phone number ID** – את זה מעתיקים ל-`WHATSAPP_PHONE_NUMBER_ID`
   - מספר טסט של Meta שאיתו אפשר לשלוח הודעות בדיקה (עד 5 נמענים מאושרים)
5. להרצה קבועה (לא רק בדיקות) צריך **Permanent Token**:
   - **Business Settings → Users → System Users → צרי System User**
   - תני לו הרשאת גישה לאפליקציה עם permission `whatsapp_business_messaging`
   - **Generate Token** ובחרי תוקף "Never Expire"
   - את הטוקן הזה שמים ב-`WHATSAPP_TOKEN`

לבסוף, כדי שהבוט יוכל לענות לכל מספר (לא רק ל-5 נמענים מאושרים),
צריך לעבור אימות עסק (**Business Verification**) ב-Meta.

## שלב 2 – הגדרת משתני הסביבה

העתיקי את `.env.example` ל-`.env` ומלאי:

```
WHATSAPP_TOKEN=<הטוקן מ-Meta>
WHATSAPP_PHONE_NUMBER_ID=<Phone Number ID מ-Meta>
VERIFY_TOKEN=<כל מחרוזת שתבחרי בעצמך, למשל "uri2024">
OWNER_PHONE=972527338868
```

## שלב 3 – הרצה מקומית (לבדיקה בלבד)

```bash
cd whatsapp-bot
npm install
npm start
```

השרת יאזין על פורט 3000. לבדיקות מקומיות עם Meta (שדורש HTTPS ציבורי)
אפשר להשתמש זמנית בכלי כמו `ngrok`.

## שלב 4 – פריסה ל-Railway (מומלץ, מארח בחינם/זול)

1. היכנסי ל-[railway.app](https://railway.app) והתחברי עם GitHub
2. **New Project → Deploy from GitHub repo** ובחרי את הריפו הזה
3. ב-**Settings → Root Directory** קבעי `whatsapp-bot`
4. ב-**Variables** הוסיפי את 4 המשתנים מהקובץ `.env.example` עם הערכים האמיתיים
5. Railway ייתן לך כתובת ציבורית כמו `https://your-app.up.railway.app`

(Render עובד באופן דומה מאוד: New → Web Service → אותו Root Directory
ואותם Environment Variables.)

## שלב 5 – חיבור ה-Webhook ב-Meta

1. חזרי ל-**WhatsApp → Configuration** באפליקציה שלך ב-Meta
2. **Edit** ליד Webhook, והזיני:
   - **Callback URL**: `https://your-app.up.railway.app/webhook`
   - **Verify Token**: אותה מחרוזת שהגדרת ב-`VERIFY_TOKEN`
3. **Verify and Save**
4. תחת **Webhook fields**, לחצי **Subscribe** על `messages`

מהרגע הזה, כל הודעה שנשלחת למספר העסקי שלך מגיעה לבוט.

## מה הבוט יודע לעשות

- **"שלום"** – מציג תפריט כפתורים (שעות / מחיר / קביעת תור)
- **"שעות" / "מחיר"** – עונה ישירות בטקסט
- **"תור" / "קביעת תור"** – מתחיל תהליך קביעת תור מלא: שם → יום (רשימה) →
  שעה פנויה (רשימה) → אישור סופי (כפתורים)
- לאחר אישור – נשלחת הודעה אליך עם כל פרטי התור
- **"תפריט"** – מאפס את השיחה בכל שלב וחוזר לתפריט הראשי
- כל הודעה אחרת שלא מזוהה – מועברת אליך בתור "הודעה חדשה מלקוח", והלקוח
  מקבל תשובה אוטומטית שתחזרי אליו

כדי לשנות שעות/מחיר, ערכי את `lib/business.js`.

## עלויות

Meta מאפשרת חלון של 24 שעות משיחה חינמית עם כל לקוח שכתב אליכם ראשון
(session messages). מעבר לזה, או כדי ליזום שיחה, נדרשים **Message
Templates** מאושרים מראש – בתעריף נמוך למסר (סדר גודל אגורות בודדות עד
כמה שקלים ל-1,000 שיחות, תלוי מדינה). לעסק קטן עם כמות הודעות סבירה,
זה בדרך כלל משמעותי פחות מ-כמה עשרות שקלים בחודש.
