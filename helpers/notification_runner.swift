import Cocoa
import Foundation

final class NotificationDelegate: NSObject, NSUserNotificationCenterDelegate {
    func userNotificationCenter(
        _ center: NSUserNotificationCenter,
        shouldPresent notification: NSUserNotification
    ) -> Bool {
        return true
    }
}

let arguments = CommandLine.arguments

guard arguments.count >= 3 else {
    FileHandle.standardError.write(
        Data("Usage: notification_runner <title> <message>\n".utf8)
    )
    exit(2)
}

let title = arguments[1]
let message = arguments[2]

let center = NSUserNotificationCenter.default
let delegate = NotificationDelegate()
center.delegate = delegate

let notification = NSUserNotification()
notification.title = title
notification.informativeText = message
notification.hasActionButton = false

center.deliver(notification)

RunLoop.current.run(until: Date(timeIntervalSinceNow: 0.5))
