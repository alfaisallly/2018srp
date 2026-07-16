# مدير Wi‑Fi — تطبيق iOS

تطبيق SwiftUI لـ iPhone يعرض **اسم شبكة Wi‑Fi المتصلة** ويدير **كلمات السر التي تُدخلها أنت** بأمان عبر Keychain.

## ⚠️ تنبيه مهم (اقرأ أولاً)

**لا يمكن لأي تطبيق على iPhone (بما في ذلك هذا) أن:**

| المطلوب | هل يمكن؟ | السبب |
|---------|----------|-------|
| قراءة كلمات سر Wi‑Fi المحفوظة في iOS | ❌ لا | Apple تحظر ذلك لحماية خصوصيتك |
| مسح جميع الشبكات المجاورة | ❌ لا | يتطلب صلاحيات خاصة لا تُمنح لـ App Store |
| اختراق شبكات الآخرين | ❌ لا | غير قانوني وغير ممكن عبر APIs الرسمية |

**ما يفعله هذا التطبيق فعلاً:**

- ✅ يعرض اسم شبكة Wi‑Fi **المتصلة حالياً**
- ✅ يحفظ كلمات السر التي **تُدخلها بنفسك** في Keychain
- ✅ يشرح كيف ترى كلمات السر المحفوظة في **إعدادات iOS**

### لعرض كلمة سر محفوظة في iOS (iOS 16+)

1. **الإعدادات** → **Wi‑Fi**
2. اضغط على (ℹ️) بجانب الشبكة
3. **كلمة السر** → Face ID / Touch ID

---

## المتطلبات

- macOS مع **Xcode 15+**
- iPhone حقيقي (محاكي Xcode لا يدعم Wi‑Fi)
- حساب Apple Developer (مجاني للتثبيت على جهازك)

---

## التثبيت على Xcode

### 1. إنشاء مشروع جديد

1. افتح Xcode → **File → New → Project**
2. اختر **iOS → App**
3. الاسم: `WiFiManager`
4. Interface: **SwiftUI** | Language: **Swift**
5. احفظ المشروع داخل مجلد `WiFiManager/` أو انسخ ملفات المصدر إليه

### 2. نسخ ملفات المصدر

انسخ محتويات هذا المجلد إلى مشروع Xcode (استبدل الملفات الافتراضية):

```
WiFiManager/
├── WiFiManagerApp.swift
├── Models/
├── Services/
├── Views/
├── Info.plist
└── WiFiManager.entitlements
```

### 3. تفعيل الصلاحيات

في Xcode → Target → **Signing & Capabilities**:

1. اضغط **+ Capability**
2. أضف **Access WiFi Information**
3. في **Info** تأكد من وجود:
   - `NSLocationWhenInUseUsageDescription`

4. في **Build Settings** → **Code Signing Entitlements**:
   ```
   WiFiManager/WiFiManager.entitlements
   ```

### 4. التشغيل

1. وصّل iPhone بالـ Mac
2. اختر جهازك من قائمة الأجهزة
3. **Run** (⌘R)
4. عند أول تشغيل: اسمح بـ **الموقع** (مطلوب لقراءة اسم الشبكة)

---

## هيكل التطبيق

```
WiFiManager/
├── WiFiManagerApp.swift          # نقطة الدخول + RTL عربي
├── Models/
│   ├── WiFiNetwork.swift         # الشبكة المتصلة
│   └── SavedNetwork.swift        # شبكة محفوظة
├── Services/
│   ├── WiFiScannerService.swift  # قراءة SSID الحالي
│   ├── KeychainService.swift     # تخزين آمن لكلمات السر
│   ├── LocationPermissionManager.swift
│   └── NetworkStore.swift        # إدارة الشبكات المحفوظة
└── Views/
    ├── ContentView.swift         # TabView رئيسي
    ├── CurrentNetworkView.swift  # الشبكة الحالية
    ├── SavedNetworksView.swift   # قائمة كلمات السر
    ├── AddNetworkView.swift      # إضافة شبكة
    ├── NetworkDetailView.swift   # تفاصيل + مشاركة
    └── SettingsGuideView.swift   # دليل iOS
```

---

## الشاشات

| التبويب | الوظيفة |
|---------|---------|
| **الشبكة الحالية** | اسم Wi‑Fi المتصل + حفظ كلمة السر |
| **كلمات السر** | قائمة الشبكات المحفوظة + بحث |
| **دليل iOS** | شرح قيود Apple وكيفية عرض كلمات السر |

---

## الأمان

- كلمات السر تُخزَّن في **iOS Keychain** (`kSecAttrAccessibleWhenUnlockedThisDeviceOnly`)
- لا تُرسل أي بيانات إلى الإنternet
- لا يمكن للتطبيق قراءة Keychain الخاص بنظام iOS

---

## حقوق التصميم والملكية

**© 2026 مهندس احمد أماجد**

جميع حقوق التصميم والواجهة والبرمجة والملكية الفكرية لهذا التطبيق محفوظة لـ **مهندس احمد أماجد**.

- **التصميم والواجهة:** مهندس احمد أماجد
- **البرمجة والتطوير:** مهندس احمد أماجد
- **اسم التطبيق:** مدير Wi‑Fi

---

## الترخيص

جميع الحقوق محفوظة © 2026 مهندس احمد أماجد — للاستخدام الشخصي بإذن صاحب الحقوق.
