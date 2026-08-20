# AGENTS.md

## Plugins Installed

### 1. Backup Plugin (`backup-plugin.ts`)
- **الوظيفة:** يسوي نسخ احتياطي تلقائي قبل تعديل أي ملف
- **المميزات:**
  - يحفظ النسخ الاحتياطي في `.opencode/backups/`
  - يحتفظ بآخر 10 نسخ فقط
  - يشتغل مع جميع أنواع الملفات

### 2. Code Review Plugin (`code-review-plugin.ts`)
- **الوظيفة:** يراجع الكود تلقائياً قبل الحفظ
- **المميزات:**
  - يكشف كلمات المرور المكتوبة في الكود
  - يكشف API Keys والأسرار
  - يقترح تحسينات الأسلوب (const/let بدلاً من var)
  - يشتغل مع TS, JS, Python, Go, Rust, Java, PHP

### 3. DB Analyzer Plugin (`db-analyzer-plugin.ts`)
- **الوظيفة:** يحلل استعلامات قواعد البيانات
- **المميزات:**
  - يكشف استعلامات SELECT, INSERT, UPDATE, DELETE
  - يحذر من مخاطر SQL Injection
  - يشتغل مع Python, JS, TS

### 4. API Detector Plugin (`api-detector-plugin.ts`)
- **الوظيفة:** يكشف نقاط نهاية API
- **المميزات:**
  - يكتشف APIs في Express, FastAPI, Django
  - يعرض Method و Path
  - يشتغل مع Python, JS, TS

### 5. Env Manager Plugin (`env-manager-plugin.ts`)
- **الوظيفة:** يدير متغيرات البيئة
- **المميزات:**
  - يكتشف استخدامات Environment Variables
  - يتحقق من ملفات .env
  - يشتغل مع Node.js, Python, Go, Rust

### 6. Docker Analyzer Plugin (`docker-analyzer-plugin.ts`)
- **الوظيفة:** يحلل ملفات Docker
- **المميزات:**
  - يحلل docker-compose.yml
  - يحلل Dockerfile
  - يكشف المشاكل الشائعة

### 7. Log Analyzer Plugin (`log-analyzer-plugin.ts`)
- **الوظيفة:** يحلل ملفات السجلات
- **المميزات:**
  - يكشف الأخطاء والتحذيرات
  - يصنف المشاكل حسب الخطورة
  - يشتغل مع جميع أنواع السجلات

### 8. Config Analyzer Plugin (`config-analyzer-plugin.ts`)
- **الوظيفة:** يحلل ملفات الإعدادات
- **المميزات:**
  - يتحقق من صحة JSON, YAML, INI
  - يكشف الأسرار المكتوبة
  - يحذر من إعدادات الإنتاج الخطيرة

### 9. Test Analyzer Plugin (`test-analyzer-plugin.ts`)
- **الوظيفة:** يحلل ملفات الاختبارات
- **المميزات:**
  - يكتشف أطر الاختبار (Jest, Pytest, JUnit)
  - يعد الاختبارات
  - يشتغل مع معظم لغات البرمجة

### 10. Import Analyzer Plugin (`import-analyzer-plugin.ts`)
- **الوظيفة:** يحلل الاستيرادات
- **المميزات:**
  - يكتشف الاستيرادات غير المستخدمة
  - يحذر من التبعيات الدائرية
  - يشتغل مع Python, JS, TS

### 11. Perf Analyzer Plugin (`perf-analyzer-plugin.ts`)
- **الوظيفة:** يحلل أداء الكود
- **المميزات:**
  - يكتشف مشاكل الأداء
  - يقترح تحسينات
  - يشتغل مع Python, JS, TS

### 12. Doc Analyzer Plugin (`doc-analyzer-plugin.ts`)
- **الوظيفة:** يحلل التوثيق
- **المميزات:**
  - يتحقق من توثيق الدوال والفئات
  - يحسب نسبة التوثيق
  - يشتغل مع Python, JS, TS

### 13. Dep Analyzer Plugin (`dep-analyzer-plugin.ts`)
- **الوظيفة:** يحلل التبعيات
- **المميزات:**
  - يتحقق من إصدارات التبعيات
  - يكتشف المشاكل المحتملة
  - يشتغل مع package.json, requirements.txt, pyproject.toml

### 14. Regex Tester Plugin (`regex-tester-plugin.ts`)
- **الوظيفة:** يختبر الأنماط النمطية (Regex)
- **المميزات:**
  - اختبار Regex مع نص
  - عرض النتائج والمطابقات
  - كشف الأخطاء

### 15. JSON Formatter Plugin (`json-formatter-plugin.ts`)
- **الوظيفة:** ينسق ويتحقق من JSON
- **المميزات:**
  - تنسيق JSON بسهولة
  - التحقق من صحة JSON
  - عرض مسار الخطأ

### 16. Test Generator Plugin (`test-generator-plugin.ts`)
- **الوظيفة:** يولّد اختبارات تلقائية
- **المميزات:**
  - توليد اختبارات لـ Python, JS, TS
  - تحليل الدوال وتوليد اختبارات لها
  - حفظ ملفات الاختبارات

### 17. Git Commit Helper Plugin (`git-commit-helper-plugin.ts`)
- **الوظيفة:** يساعد في كتابة Commit Messages
- **المميزات:**
  - تحليل التغييرات تلقائياً
  - اقتراح نوع Commit
  - توليد رسالة Commit مناسبة

### 18. Snippet Manager Plugin (`snippet-manager-plugin.ts`)
- **الوظيفة:** يدير وأكواد محفوظة
- **المميزات:**
  - حفظ واسترجاع Snippets
  - البحث في Snippets
  - تصنيف حسب اللغة والـ Tags

### 19. Base64 Plugin (`base64-plugin.ts`)
- **الوظيفة:** تشفير وفك تشفير Base64
- **المميزات:**
  - تشفير نص إلى Base64
  - فك تشفير Base64 إلى نص
  - التحقق من صحة Base64

### 20. Hash Plugin (`hash-plugin.ts`)
- **الوظيفة:** توليد تجزئة (Hash)
- **المميزات:**
  - دعم MD5, SHA1, SHA256, SHA512
  - توليد Hash لنصوص وملفات
  - التحقق من Hash

### 21. Timestamp Plugin (`timestamp-plugin.ts`)
- **الوظيفة:** تحويل الوقت
- **المميزات:**
  - تحويل timestamps إلى تواريخ
  - تحويل Unix timestamps
  - عرض الوقت الحالي

### 22. Diff Plugin (`diff-plugin.ts`)
- **الوظيفة:** مقارنة الملفات
- **المميزات:**
  - مقارنة ملفين
  - عرض الفروقات
  - تحليل التغييرات

### 23. Lorem Plugin (`lorem-plugin.ts`)
- **الوظيفة:** توليد نصوص مؤقتة
- **المميزات:**
  - توليد كلمات وجمل وفقرات
  - تخصيص العدد والنوع
  - نصوص Lorem Ipsum

### 24. Web Search Plugin (`web-search-plugin.ts`)
- **الوظيفة:** البحث في المواقع
- **المميزات:**
  - البحث في محركات البحث
  - عرض النتائج
  - جلب معلومات من المواقع

### 25. URL Fetcher Plugin (`url-fetcher-plugin.ts`)
- **الوظيفة:** جلب محتوى من URLs
- **المميزات:**
  - جلب صفحات الويب
  - تحليل المحتوى
  - استخراج المعلومات

### 26. HTTP Client Plugin (`http-client-plugin.ts`)
- **الوظيفة:** إجراء طلبات HTTP
- **المميزات:**
  - GET, POST, PUT, DELETE
  - تحليل الاستجابات
  - إدارة Headers

### 27. Password Generator Plugin (`password-generator-plugin.ts`)
- **الوظيفة:** توليد كلمات مرور
- **المميزات:**
  - توليد كلمات مرور قوية
  - تخصيص الطول والتعقيد
  - التحقق من قوة كلمة المرور

### 28. UUID Generator Plugin (`uuid-generator-plugin.ts`)
- **الوظيفة:** توليد UUIDs
- **المميزات:**
  - توليد UUIDs فريدة
  - دعم الإصدارات المختلفة
  - التحقق من صحة UUID

### 29. Color Converter Plugin (`color-converter-plugin.ts`)
- **الوظيفة:** تحويل الألوان
- **المميزات:**
  - تحويل بين Hex, RGB, HSL
  - تحليل الألوان
  - توليد لوحات ألوان

### 30. Markdown Converter Plugin (`markdown-converter-plugin.ts`)
- **الوظيفة:** تحويل Markdown إلى HTML
- **المميزات:**
  - تحويل Markdown إلى HTML
  - تحويل HTML إلى Markdown
  - معاينة المحتوى

### 31. CSV Analyzer Plugin (`csv-analyzer-plugin.ts`)
- **الوظيفة:** تحليل ملفات CSV
- **المميزات:**
  - تحليل البيانات
  - البحث والفلترة
  - تحليل الإحصائيات

### 32. XML Analyzer Plugin (`xml-analyzer-plugin.ts`)
- **الوظيفة:** تحليل ملفات XML
- **المميزات:**
  - التحقق من صحة XML
  - تنسيق XML
  - تحويل XML إلى JSON

### 33. YAML Analyzer Plugin (`yaml-analyzer-plugin.ts`)
- **الوظيفة:** تحليل ملفات YAML
- **المميزات:**
  - التحقق من صحة YAML
  - تنسيق YAML
  - تحويل YAML إلى JSON

### 34. Regex Builder Plugin (`regex-builder-plugin.ts`)
- **الوظيفة:** بناء أنماط Regex
- **المميزات:**
  - بناء Regex
  - شرح الأنماط
  - أنماط شائعة جاهزة

### 35. Cron Builder Plugin (`cron-builder-plugin.ts`)
- **الوظيفة:** بناء Cron Expressions
- **المميزات:**
  - بناء Cron Expressions
  - شرح التعبيرات
  - تعبيرات شائعة جاهزة

### 36. URL Encoder Plugin (`url-encoder-plugin.ts`)
- **الوظيفة:** تشفير وفك تشفير URLs
- **المميزات:**
  - تشفير URLs
  - فك تشفير URLs
  - إدارة Query Strings

### 37. HTML Entity Plugin (`html-entity-plugin.ts`)
- **الوظيفة:** تشفير وفك تشفير HTML Entities
- **المميزات:**
  - تشفير HTML Entities
  - فك تشفير HTML Entities
  - إدارة الرموز الخاصة

### 38. Plugin Tester Plugin (`plugin-tester-plugin.ts`)
- **الوظيفة:** اختبار جميع البلوگنات واكتشاف المشاكل
- **المميزات:**
  - اختبار صحة الكود لكل بلوگن
  - اكتشاف الأخطاء والتحذيرات
  - تقرير مفصل عن حالة كل بلوگن
  - إحصائيات شاملة للبلوگنات

### 39. Playwright MCP
- **الوظيفة:** يمكّن من رؤية المتصفح والتعامل معه
- **الأوامر المتاحة:**
  - فتح صفحات ويب
  - النقر على العناصر
  - ملء النماذج
  - التقاط لقطات شاشة

### 39. GitHub MCP
- **الوظيفة:** إدارة المستودعات والـ Issues والـ Pull Requests
- **الأوامر المتاحة:**
  - إنشاء Issues و Pull Requests
  - مراجعة التغييرات
  - إدارة الفروع

### 40. System Monitor Plugin (`system-monitor-plugin.ts`)
- **الوظيفة:** عرض معلومات النظام
- **المميزات:**
  - عرض معلومات CPU, RAM, Disk
  - عرض معلومات النظام (Uptime, Hostname)
  - أوامر: `sys`, `cpu`, `ram`, `disk`, `uptime`

### 41. File Manager Plugin (`file-manager-plugin.ts`)
- **الوظيفة:** إدارة الملفات والمجلدات
- **المميزات:**
  - تصفح المجلدات
  - عرض معلومات الملفات
  - البحث عن ملفات
  - حساب حجم المجلدات
  - أوامر: `ls`, `fi`, `find`, `du`, `cd~`, `cd Desktop`

### 42. Process Manager Plugin (`process-manager-plugin.ts`)
- **الوظيفة:** إدارة العمليات (Processes)
- **المميزات:**
  - عرض العمليات الشغالة
  - البحث عن عمليات
  - عرض معلومات عملية
  - اغلاق عمليات
  - أوامر: `ps`, `ps find`, `ps info`, `ps kill`, `top`

### 43. Network Monitor Plugin (`network-monitor-plugin.ts`)
- **الوظيفة:** مراقبة الشبكة
- **المميزات:**
  - عرض واجهات الشبكة
  - عرض الاتصالات النشطة
  - فحص DNS
  - عرض IP العام
  - عرض المنافذ المفتوحة
  - فحص WiFi
  - أوامر: `net`, `net conn`, `ping`, `dns`, `myip`, `ports`, `wifi`

### 44. Installed Apps Plugin (`installed-apps-plugin.ts`)
- **الوظيفة:** عرض البرامج المثبتة
- **المميزات:**
  - عرض جميع البرامج المثبتة
  - البحث عن برنامج
  - عرض حزم Python
  - عرض حزم NPM
  - أوامر: `apps`, `apps search`, `pip list`, `npm list`

### 45. Services Manager Plugin (`services-manager-plugin.ts`)
- **الوظيفة:** إدارة الخدمات (Services)
- **المميزات:**
  - عرض الخدمات النشطة
  - عرض الخدمات المتوقفة
  - عرض معلومات خدمة
  - تشغيل/ايقاف/اعادة تشغيل خدمة
  - أوامر: `services`, `svc info`, `svc stop`, `svc start`, `svc restart`, `boot`

### 46. Quick Control Plugin (`quick-control-plugin.ts`)
- **الوظيفة:** تحكم سريع بالكمبيوتر
- **المميزات:**
  - عرض احصائيات سريعة
  - اغلاق/اعادة تشغيل الكمبيوتر
  - الغاء عملية الاغلاق
  - عرض Hostname
  - أوامر: `qs`, `sys shutdown`, `sys restart`, `sys cancel`, `hostname`

### 47. OpenBrowser Plugin (`openbrowser-plugin.ts`)
- **الوظيفة:** متصفح متكامل مدمج مع opencode
- **المميزات:**
  - متصفح كامل بتصميم opencode (ثيم اسود)
  - شريط عناوين ذكي
  - ازرار تنقل (امام/خلف/تحديث/الرئيسية)
  - شريط اشارات مرجعية
  - سجل التصفح
  - التقاط لقطات شاشة
  - أوامر: `browser`, `browse <url>`

### 48. Window Manager Plugin (`window-manager-plugin.ts`)
- **الوظيفة:** عرض النوافذ المفتوحة على النظام
- **المميزات:**
  - عرض جميع النوافذ المفتوحة مع التفاصيل
  - عرض عناوين النوافذ فقط
  - معلومات الذاكرة لكل نافذة
  - أوامر: `windows`, `windows titles`

### 49. Clipboard Manager Plugin (`clipboard-manager-plugin.ts`)
- **الوظيفة:** إدارة الحافظة (Clipboard)
- **المميزات:**
  - عرض محتوى الحافظة
  - نسخ نص للحافظة
  - مسح الحافظة
  - أوامر: `clip`, `clip set`, `clip clear`

### 50. Screenshot Plugin (`screenshot-plugin.ts`)
- **الوظيفة:** التقاط لقطات شاشة
- **المميزات:**
  - التقاط شاشة كاملة
  - التقاط منطقة محددة
  - حفظ في المجلد المؤقت
  - أوامر: `screenshot`, `screenshot area`

### 51. Audio Control Plugin (`audio-control-plugin.ts`)
- **الوظيفة:** التحكم بالصوت
- **المميزات:**
  - عرض مستوى الصوت
  - رفع/خفض الصوت
  - كتم الصوت
  - أوامر: `vol`, `vol up`, `vol down`, `vol mute`

### 52. Brightness Plugin (`brightness-plugin.ts`)
- **الوظيفة:** التحكم بالسطوع
- **المميزات:**
  - عرض مستوى السطوع
  - رفع/خفض السطوع
  - أوامر: `brightness`, `brightness up`, `brightness down`

### 53. Calculator Plugin (`calculator-plugin.ts`)
- **الوظيفة:** آلة حاسبة
- **المميزات:**
  - حساب تعبيرات رياضية
  - دعم الجمع والطرح والضرب والقسمة
  - أوامر: `calc <expression>`

### 54. Unit Converter Plugin (`unit-converter-plugin.ts`)
- **الوظيفة:** تحويل الوحدات
- **المميزات:**
  - تحويل الطول والوزن والحرارة
  - وحدات متعددة
  - أوامر: `convert <value> <from> to <to>`

### 55. Timer Plugin (`timer-plugin.ts`)
- **الوظيفة:** مؤقت و عد تنازلي
- **المميزات:**
  - عد تنازلي بأيام
  - ميزانية مدمجة
  - أوامر: `timer <seconds>`, `stopwatch`

### 56. Weather Plugin (`weather-plugin.ts`)
- **الوظيفة:** عرض حالة الطقس
- **المميزات:**
  - عرض الطقس الحالي
  - درجة الحرارة والرطوبة
  - أوامر: `weather`

### 57. IP Info Plugin (`ip-info-plugin.ts`)
- **الوظيفة:** معلومات الـ IP
- **المميزات:**
  - عرض IP المحلي
  - عرض IP العام
  - الموقع الجغرافي
  - أوامر: `ip`, `ip public`, `ip geo`

### 58. DNS Tools Plugin (`dns-tools-plugin.ts`)
- **الوظيفة:** أدوات DNS
- **المميزات:**
  - استعلام DNS
  - تغيير خادم DNS
  - أوامر: `dns <domain>`, `dns change`

### 59. WiFi Manager Plugin (`wifi-manager-plugin.ts`)
- **الوظيفة:** إدارة الشبكات اللاسلكية
- **المميزات:**
  - عرض الشبكات المتاحة
  - الاتصال/القطع
  - عرض كلمة المرور
  - أوامر: `wifi`, `wifi connect`, `wifi disconnect`, `wifi password`

### 60. Bluetooth Manager Plugin (`bluetooth-manager-plugin.ts`)
- **الوظيفة:** إدارة البلوتوث
- **المميزات:**
  - عرض الأجهزة
  - البحث عن أجهزة
  - تشغيل/إيقاف
  - أوامر: `bt`, `bt scan`, `bt on`, `bt off`

### 61. Process Killer Plugin (`process-killer-plugin.ts`)
- **الوظيفة:** إغلاق العمليات
- **المميزات:**
  - إغلاق عملية بالاسم
  - إغلاق عملية بالرقم
  - أوامر: `kill <name>`, `kill id <pid>`

### 62. Disk Space Plugin (`disk-space-plugin.ts`)
- **الوظيفة:** إدارة مساحة القرص
- **المميزات:**
  - عرض جميع الأقراص
  - تفاصيل قرص محدد
  - تنظيف مؤقت
  - أوامر: `disk`, `disk detail`, `disk clean`

### 63. Startup Manager Plugin (`startup-manager-plugin.ts`)
- **الوظيفة:** إدارة برامج التشغيل
- **المميزات:**
  - عرض برامج التشغيل
  - إضافة/إزالة برنامج
  - أوامر: `startup`, `startup add`, `startup remove`

### 64. Event Log Plugin (`event-log-plugin.ts`)
- **الوظيفة:** سجل أحداث Windows
- **المميزات:**
  - عرض الأخطاء الأخيرة
  - عرض التحذيرات
  - عدد مخصص
  - أوامر: `events`, `events warnings`, `events <count>`

### 65. Scheduled Tasks Plugin (`scheduled-tasks-plugin.ts`)
- **الوظيفة:** إدارة المهام المجدولة
- **المميزات:**
  - عرض المهام
  - معلومات مهمة
  - تشغيل مهمة
  - أوامر: `tasks`, `task info`, `task run`

### 66. Firewall Plugin (`firewall-plugin.ts`)
- **الوظيفة:** إدارة جدار الحماية
- **المميزات:**
  - عرض الحالة
  - حظر/سماح لتطبيق
  - أوامر: `firewall`, `firewall block`, `firewall allow`

### 67. Environment Vars Plugin (`environment-vars-plugin.ts`)
- **الوظيفة:** إدارة متغيرات البيئة
- **المميزات:**
  - عرض جميع المتغيرات
  - جلب/تعيين/حذف متغير
  - أوامر: `env`, `env get`, `env set`, `env delete`

### 68. ZIP Manager Plugin (`zip-manager-plugin.ts`)
- **الوظيفة:** إدارة ملفات ZIP
- **المميزات:**
  - إنشاء أرشيف
  - استخراج أرشيف
  - أوامر: `zip`, `unzip`

### 69. File Hash Plugin (`file-hash-plugin.ts`)
- **الوظيفة:** حساب Hash للملفات
- **المميزات:**
  - MD5 و SHA256
  - التحقق من سلامة الملف
  - أوامر: `hash <file>`, `hash md5`, `hash sha256`

### 70. File Search Plugin (`file-search-plugin.ts`)
- **الوظيفة:** البحث عن ملفات
- **المميزات:**
  - البحث بالاسم
  - البحث في محتوى الملفات
  - أوامر: `search`, `search content`

### 71. Duplicate Finder Plugin (`duplicate-finder-plugin.ts`)
- **الوظيفة:** إيجاد الملفات المكررة
- **المميزات:**
  - البحث بالـ Hash
  - عرض الملفات المتشابهة
  - أوامر: `dupes <dir>`

### 72. Folder Size Plugin (`folder-size-plugin.ts`)
- **الوظيفة:** حساب حجم المجلدات
- **المميزات:**
  - حجم مجلد محدد
  - أكبر المجلدات
  - أوامر: `size <dir>`, `size top`

### 73. Recent Files Plugin (`recent-files-plugin.ts`)
- **الوظيفة:** الملفات الأخيرة
- **المميزات:**
  - عرض الملفات الأخيرة
  - ملفات التنزيل
  - المستندات
  - أوامر: `recent`, `recent downloads`, `recent docs`

### 74. Text-to-Speech Plugin (`text-to-speech-plugin.ts`)
- **الوظيفة:** تحويل النص إلى كلام
- **المميزات:**
  - نطق أي نص
  - إيقاف النطق
  - أوامر: `speak <text>`, `speak stop`

### 75. Color Picker Plugin (`color-picker-plugin.ts`)
- **الوظيفة:** منتقي الألوان
- **المميزات:**
  - التقاط لون من الشاشة
  - عرض معلومات اللون
  - أوامر: `color pick`, `color hex`

### 76. Keyboard Shortcuts Plugin (`keyboard-shortcuts-plugin.ts`)
- **الوظيفة:** اختصارات لوحة المفاتيح
- **المميزات:**
  - عرض الاختصارات الشائعة
  - ضغط مفتاح
  - أوامر: `shortcuts`, `shortcut press`

### 77. Power Options Plugin (`power-options-plugin.ts`)
- **الوظيفة:** خيارات الطاقة
- **المميزات:**
  - حالة البطارية
  - خطط الطاقة
  - وضع التوفير/الأداء
  - أوامر: `power`, `power plan`, `power save`, `power performance`

### 78. System Info Plugin (`system-info-plugin.ts`)
- **الوظيفة:** معلومات النظام التفصيلية
- **المميزات:**
  - معلومات شاملة
  - CPU/RAM/GPU/Disk
  - أوامر: `sysinfo`, `sysinfo cpu`, `sysinfo ram`, `sysinfo gpu`, `sysinfo disk`

### 79. Running Time Plugin (`running-time-plugin.ts`)
- **الوظيفة:** وقت التشغيل
- **المميزات:**
  - وقت تشغيل النظام
  - وقت تشغيل عملية
  - أوامر: `uptime`, `uptime <process>`

### 80. Hostname Plugin (`hostname-plugin.ts`)
- **الوظيفة:** إدارة اسم الكمبيوتر
- **المميزات:**
  - عرض الاسم
  - تغيير الاسم
  - أوامر: `hostname`, `hostname set`

### 81. Whoami Plugin (`whoami-plugin.ts`)
- **الوظيفة:** معلومات المستخدم الحالي
- **المميزات:**
  - معلومات المستخدم
  - المجموعات
  - أوامر: `whoami`, `whoami groups`

### 82. Network Speed Plugin (`network-speed-plugin.ts`)
- **الوظيفة:** قياس سرعة الإنترنت
- **المميزات:**
  - سرعة التحميل والرفع
  - اختبار السرعة المحلية
  - أوامر: `speed`, `speed local`

### 83. Port Scanner Plugin (`port-scanner-plugin.ts`)
- **الوظيفة:** مسح المنافذ
- **المميزات:**
  - مسح المنافذ الشائعة
  - مسح منفذ محدد
  - أوامر: `scan <host>`, `scan <host> <port>`

### 84. SSH Manager Plugin (`ssh-manager-plugin.ts`)
- **الوظيفة:** إدارة SSH
- **المميزات:**
  - الاتصال بخادم
  - إنشاء مفتاح
  - عرض المفاتيح
  - أوامر: `ssh`, `ssh keygen`, `ssh keys`

### 85. Git Quick Plugin (`git-quick-plugin.ts`)
- **الوظيفة:** أوامر Git سريعة
- **المميزات:**
  - status/push/pull/log
  - أوامر مختصرة
  - أوامر: `gq status`, `gq push`, `gq pull`, `gq log`

### 86. NPM Quick Plugin (`npm-quick-plugin.ts`)
- **الوظيفة:** أوامر NPM سريعة
- **المميزات:**
  - تثبيت الحزم
  - تشغيل السكربتات
  - عرض الحزم القديمة
  - أوامر: `nq install`, `nq run`, `nq list`, `nq outdated`

### 87. Python Quick Plugin (`python-quick-plugin.ts`)
- **الوظيفة:** أوامر Python سريعة
- **المميزات:**
  - تشغيل ملفات
  - تثبيت الحزم
  - إدارة البيئة الافتراضية
  - أوامر: `pq run`, `pq install`, `pq list`, `pq venv`

### 88. Todo Plugin (`todo-plugin.ts`)
- **الوظيفة:** إدارة قائمة المهام
- **المميزات:**
  - عرض المهام
  - إضافة/حذف/إنجاز مهمة
  - حفظ في ملف
  - أوامر: `todo`, `todo add`, `todo done`, `todo remove`

### 89. File Watcher Plugin (`file-watcher-plugin.ts`)
- **الوظيفة:** متابعة تغييرات الملفات
- **المميزات:**
  - متابعة مجلد للتغييرات
  - إيقاف المتابعة
  - عرض المجلدات المتابع
  - أوامر: `watch <dir>`, `watch stop`, `watch list`

### 90. Notification Plugin (`notification-plugin.ts`)
- **الوظيفة:** إرسال إشعارات ويندوز
- **المميزات:**
  - إرسال إشعار بعنوان ورسالة
  - إشعارات toast
  - أوامر: `notify <title> <message>`

### 91. App Launcher Plugin (`app-launcher-plugin.ts`)
- **الوظيفة:** تشغيل البرامج
- **المميزات:**
  - فتح برنامج بالاسم
  - فتح رابط في المتصفح
  - فتح مجلد
  - عرض البرامج المثبتة
  - أوامر: `open <app>`, `open url <url>`, `open folder <path>`, `apps list`

### 92. Notes Plugin (`notes-plugin.ts`)
- **الوظيفة:** نظام ملاحظات سريع
- **المميزات:**
  - إضافة ملاحظة
  - عرض الملاحظات
  - حذف ملاحظة
  - مسح الكل
  - حفظ في ملف
  - أوامر: `note add`, `note list`, `note remove`, `note clear`

### 93. Clipboard Watcher Plugin (`clipboard-watcher-plugin.ts`)
- **الوظيفة:** متابعة تغييرات الحافظة
- **المميزات:**
  - بدء المتابعة
  - إيقاف المتابعة
  - عرض سجل الحافظة
  - حفظ آخر 10 تغييرات
  - أوامر: `clipwatch`, `clipwatch stop`, `clipwatch list`

### 94. System Actions Plugin (`system-actions-plugin.ts`)
- **الوظيفة:** إجراءات النظام السريعة
- **المميزات:**
  - قفل الكمبيوتر
  - إيقاف مؤقت
  - سبات
  - إعادة تشغيل
  - إيقاف التشغيل
  - تسجيل خروج
  - تفريغ سلة المهملات
  - أوامر: `lock`, `sleep`, `hibernate`, `restart`, `shutdown`, `logoff`, `empty trash`

## Skills Available

### 1. CloudMesh Helper
- **متى يستخدم:** عند العمل على مشروع CloudMesh
- **المحتوى:** أوامر شائعة، هيكل المشروع، اختبارات، نشر

### 2. Security Review
- **متى يستخدم:** عند مراجعة الكود للأمان
- **المحتوى:** فحص كلمات المرور، SQL Injection، XSS، Command Injection

### 3. Git Workflow
- **متى يستخدم:** عند التعامل مع Git
- **المحتوى:** صيغة Commit، أوامر شائعة، سير العمل

## Permissions

### مسموح به:
- `git *` - جميع أوامر Git
- `npm *` - جميع أوامر npm
- `npx *` - جميع أوامر npx
- `pip *` - جميع أوامر pip
- `python *` - جميع أوامر Python
- `cm *` - جميع أوامر CloudMesh
- `*` - جميع الأوامر (Full Access)