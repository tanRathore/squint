import SwiftUI
import AppIntents
import UserNotifications

@main
struct SquintApp: App {
    @UIApplicationDelegateAdaptor(PushDelegate.self) var pushDelegate

    init() {
        SquintShortcuts.updateAppShortcutParameters()
    }

    var body: some Scene {
        WindowGroup {
            SetupView()
        }
    }
}

final class PushDelegate: NSObject, UIApplicationDelegate, UNUserNotificationCenterDelegate {
    func application(_ application: UIApplication, didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]? = nil) -> Bool {
        UNUserNotificationCenter.current().delegate = self
        UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .sound, .timeSensitive]) { granted, _ in
            guard granted else { return }
            DispatchQueue.main.async { application.registerForRemoteNotifications() }
        }
        return true
    }

    func application(_ application: UIApplication, didRegisterForRemoteNotificationsWithDeviceToken deviceToken: Data) {
        let token = deviceToken.map { String(format: "%02x", $0) }.joined()
        Task { await SquintClient().registerPush(token: token) }
    }

    func userNotificationCenter(_ center: UNUserNotificationCenter, willPresent notification: UNNotification) async -> UNNotificationPresentationOptions {
        Haptics.shared.play(pattern: [0, 650], amplitudes: [0, 255])
        return [.banner, .sound]
    }
}

struct SquintShortcuts: AppShortcutsProvider {
    static var appShortcuts: [AppShortcut] {
        AppShortcut(
            intent: CheckImageIntent(),
            phrases: ["Check this with \(.applicationName)", "Is this AI with \(.applicationName)"],
            shortTitle: "Check image",
            systemImageName: "eye.trianglebadge.exclamationmark"
        )
        AppShortcut(
            intent: CheckTextIntent(),
            phrases: ["Check this text with \(.applicationName)"],
            shortTitle: "Check text",
            systemImageName: "text.magnifyingglass"
        )
    }
}
