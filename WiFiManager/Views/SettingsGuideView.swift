import SwiftUI

struct SettingsGuideView: View {
    private let steps: [(title: String, detail: String, icon: String)] = [
        (
            "افتح الإعدادات",
            "انتقل إلى تطبيق «الإعدادات» على الآيفون.",
            "gearshape.fill"
        ),
        (
            "Wi‑Fi",
            "اضغط على «Wi‑Fi» ثم على اسم الشبكة المتصلة (أو المحفوظة).",
            "wifi"
        ),
        (
            "كلمة السر",
            "في iOS 16 وما بعده، اضغط «كلمة السر» ثم Face ID / Touch ID لعرضها.",
            "faceid"
        ),
        (
            "iCloud Keychain",
            "إذا كانت الشبكة متزامنة، قد تجد كلمة السر أيضاً في Keychain Access على Mac.",
            "icloud.fill"
        )
    ]

    var body: some View {
        NavigationStack {
            List {
                Section {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("كيف أرى كلمة سر محفوظة في iOS؟")
                            .font(.headline)

                        Text("Apple تسمح فقط لتطبيق «الإعدادات» بعرض كلمات السر المحفوظة في النظام — وليس للتطبيقات الخارجية.")
                            .font(.subheadline)
                            .foregroundStyle(.secondary)
                    }
                    .padding(.vertical, 4)
                }

                Section("الخطوات") {
                    ForEach(Array(steps.enumerated()), id: \.offset) { index, step in
                        HStack(alignment: .top, spacing: 12) {
                            ZStack {
                                Circle()
                                    .fill(Color.accentColor.opacity(0.15))
                                    .frame(width: 36, height: 36)
                                Image(systemName: step.icon)
                                    .foregroundStyle(Color.accentColor)
                            }

                            VStack(alignment: .leading, spacing: 4) {
                                Text("\(index + 1). \(step.title)")
                                    .font(.headline)
                                Text(step.detail)
                                    .font(.subheadline)
                                    .foregroundStyle(.secondary)
                            }
                        }
                        .padding(.vertical, 4)
                    }
                }

                Section("ما الذي يفعله هذا التطبيق؟") {
                    FeatureRow(icon: "checkmark.circle.fill", text: "يعرض اسم شبكة Wi‑Fi المتصلة حالياً", positive: true)
                    FeatureRow(icon: "checkmark.circle.fill", text: "يحفظ كلمات السر التي تُدخلها أنت بأمان", positive: true)
                    FeatureRow(icon: "checkmark.circle.fill", text: "يسمح بمشاركة كلمات السر المحفوظة", positive: true)
                    FeatureRow(icon: "xmark.circle.fill", text: "لا يمسح الشبكات المجاورة", positive: false)
                    FeatureRow(icon: "xmark.circle.fill", text: "لا يقرأ كلمات سر iOS المحفوظة", positive: false)
                    FeatureRow(icon: "xmark.circle.fill", text: "لا يخترق شبكات الآخرين", positive: false)
                }

                Section("لماذا؟") {
                    Text("حماية خصوصيتك. لو استطاع أي تطبيق قراءة كلمات سر Wi‑Fi، لكان بإمكان التطبيقات الخبيثة سرقة شبكتك.")
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                }
            }
            .navigationTitle("دليل iOS")
        }
    }
}

private struct FeatureRow: View {
    let icon: String
    let text: String
    let positive: Bool

    var body: some View {
        Label {
            Text(text)
        } icon: {
            Image(systemName: icon)
                .foregroundStyle(positive ? .green : .red)
        }
    }
}

#Preview {
    SettingsGuideView()
        .environment(\.layoutDirection, .rightToLeft)
}
