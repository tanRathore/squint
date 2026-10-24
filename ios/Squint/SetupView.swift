import SwiftUI

struct SetupView: View {
    @State private var server = Settings.server
    @State private var speak = Settings.speak
    @State private var earcons = Settings.earcons
    @State private var offline = Settings.offline
    @State private var tutorialDone = Settings.tutorialDone
    @State private var recent = Settings.recent
    @State private var showDetail = false
    @State private var detailTitle = ""
    @State private var detailBody = ""
    @State private var flagged: Set<String> = []

    var body: some View {
        NavigationStack {
            List {
                Section {
                    Text("Press the Action Button (or double-tap the back of your phone) on anything. One long buzz means it looks machine made, two short means nothing points to AI, three quick taps means it couldn't tell. Press again on the same thing to say we got it wrong.")
                        .font(.callout)
                    Text("Nothing is saved. The screenshot is checked in memory and only a fingerprint is kept.")
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                }

                Section("Set it up") {
                    step(done: true, "Install the “Squint the screen” shortcut", "Shortcuts → Take Screenshot → Check with squint")
                    step(done: true, "Settings → Action Button → Shortcut → Squint the screen", nil)
                    step(done: true, "or Accessibility → Touch → Back Tap → Squint the screen", nil)
                    step(done: tutorialDone, "Feel the three answers once", nil)
                    Button("Feel the three answers") { tutorial() }
                    Link("Get the shortcut", destination: URL(string: "https://www.icloud.com/shortcuts/squint-placeholder")!)
                }

                Section("Options") {
                    TextField("Server", text: $server)
                        .textInputAutocapitalization(.never)
                        .keyboardType(.URL)
                        .onChange(of: server) { _, v in Settings.server = v }
                    Toggle("Whisper the verdict out loud", isOn: $speak)
                        .onChange(of: speak) { _, v in Settings.speak = v }
                    Toggle("Also play a tone (phone on a table)", isOn: $earcons)
                        .onChange(of: earcons) { _, v in Settings.earcons = v; if v { Earcons.shared.play(pattern: [0, 110, 110, 110], amplitudes: [0, 160, 0, 160]) } }
                    Toggle("Answer from the phone alone when offline", isOn: $offline)
                        .onChange(of: offline) { _, v in Settings.offline = v }
                    Button("New anonymous id") {
                        Settings.rotateId()
                        Haptics.shared.ack()
                    }
                }

                Section("Recent checks on this phone") {
                    if recent.isEmpty {
                        Text("nothing yet").foregroundStyle(.secondary)
                    }
                    ForEach(Array(recent.enumerated()), id: \.offset) { _, row in
                        HStack {
                            VStack(alignment: .leading) {
                                Text(row["headline"] as? String ?? "")
                                Text(row["app"] as? String ?? "").font(.caption).foregroundStyle(.secondary)
                            }
                            .contentShape(Rectangle())
                            .onTapGesture {
                                guard let id = row["id"] as? String else { return }
                                Task {
                                    let v = await SquintClient().details(checkId: id)
                                    detailTitle = v?.headline ?? (row["headline"] as? String ?? "")
                                    detailBody = v.map { ([$0.say] + $0.evidence.map { "•  \($0)" }).joined(separator: "\n\n") } ?? "Couldn't fetch the details for this check. It may have been purged, or the server is unreachable."
                                    showDetail = true
                                }
                            }
                            Spacer()
                            if let id = row["id"] as? String, !flagged.contains(id), !id.hasPrefix("local-") {
                                Button("wrong") {
                                    flagged.insert(id)
                                    Task { await SquintClient().feedback(checkId: id, label: "unsure") }
                                }
                                .font(.caption)
                                .buttonStyle(.bordered)
                            }
                        }
                    }
                }
            }
            .navigationTitle("squint")
            .alert(detailTitle, isPresented: $showDetail) {
                Button("OK", role: .cancel) {}
            } message: {
                Text(detailBody)
            }
            .onAppear { recent = Settings.recent; tutorialDone = Settings.tutorialDone }
        }
    }

    private func step(done: Bool, _ title: String, _ detail: String?) -> some View {
        HStack(alignment: .top) {
            Image(systemName: done ? "checkmark.circle.fill" : "circle").foregroundStyle(done ? .green : .secondary)
            VStack(alignment: .leading) {
                Text(title)
                if let detail { Text(detail).font(.caption).foregroundStyle(.secondary) }
            }
        }
        .accessibilityElement(children: .combine)
    }

    private func tutorial() {
        let steps: [(String, [Int], [Int], Double)] = [
            ("This is likely AI: one long buzz.", [0, 650], [0, 255], 0),
            ("This is can't tell: three quick taps.", [0, 70, 70, 70, 70, 70], [0, 200, 0, 200, 0, 200], 2.6),
            ("This is nothing points to AI: two short.", [0, 110, 110, 110], [0, 160, 0, 160], 5.2),
        ]
        for (line, pat, amp, delay) in steps {
            DispatchQueue.main.asyncAfter(deadline: .now() + delay) {
                Whisper.shared.say(line)
                DispatchQueue.main.asyncAfter(deadline: .now() + 1.5) {
                    Haptics.shared.play(pattern: pat, amplitudes: amp)
                    Earcons.shared.play(pattern: pat, amplitudes: amp)
                }
            }
        }
        Settings.tutorialDone = true
        tutorialDone = true
    }
}
