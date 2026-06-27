import AppKit
import Foundation

struct ReviewPayload: Decodable {
    let title: String
    let message: String
    let fields: [ReviewField]
}

struct ReviewField: Decodable {
    let label: String
    let value: String
}

struct ReviewResult: Encodable {
    let action: String
    let values: [String]
}

final class ReviewDialog: NSObject {
    private let payload: ReviewPayload
    private var fields: [NSTextField] = []
    private var result = ReviewResult(action: "skip", values: [])
    private var window: NSWindow?

    init(payload: ReviewPayload) {
        self.payload = payload
    }

    func run() -> ReviewResult {
        NSApp.setActivationPolicy(.accessory)
        buildWindow()
        guard let window else {
            return result
        }
        NSApp.activate(ignoringOtherApps: true)
        window.makeKeyAndOrderFront(nil)
        if let firstField = fields.first {
            window.makeFirstResponder(firstField)
        }
        NSApp.runModal(for: window)
        window.orderOut(nil)
        return result
    }

    private func buildWindow() {
        let fieldCount = max(payload.fields.count, 1)
        let fieldHeight: CGFloat = 34
        let contentWidth: CGFloat = 560
        let messageHeight = measuredHeight(
            payload.message,
            width: contentWidth - 40,
            font: .systemFont(ofSize: 13)
        )
        let contentHeight = max(
            220,
            94 + messageHeight + CGFloat(fieldCount) * fieldHeight + 56
        )

        let window = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: contentWidth, height: contentHeight),
            styleMask: [.titled, .closable],
            backing: .buffered,
            defer: false
        )
        window.title = payload.title
        window.isReleasedWhenClosed = false
        window.center()

        let root = NSView(frame: NSRect(x: 0, y: 0, width: contentWidth, height: contentHeight))
        window.contentView = root

        let titleLabel = NSTextField(labelWithString: payload.title)
        titleLabel.font = .systemFont(ofSize: 18, weight: .semibold)
        titleLabel.frame = NSRect(
            x: 20,
            y: contentHeight - 44,
            width: contentWidth - 40,
            height: 24
        )
        root.addSubview(titleLabel)

        let messageLabel = NSTextField(wrappingLabelWithString: payload.message)
        messageLabel.font = .systemFont(ofSize: 13)
        messageLabel.textColor = .secondaryLabelColor
        messageLabel.frame = NSRect(
            x: 20,
            y: contentHeight - 58 - messageHeight,
            width: contentWidth - 40,
            height: messageHeight
        )
        root.addSubview(messageLabel)

        let fieldTop = contentHeight - 76 - messageHeight
        for (index, field) in payload.fields.enumerated() {
            let y = fieldTop - CGFloat(index + 1) * fieldHeight

            let label = NSTextField(labelWithString: "\(field.label):")
            label.alignment = .right
            label.font = .systemFont(ofSize: 13)
            label.frame = NSRect(x: 20, y: y + 5, width: 132, height: 22)
            root.addSubview(label)

            let input = NSTextField(frame: NSRect(x: 164, y: y, width: 376, height: 26))
            input.stringValue = field.value
            input.isEditable = true
            input.isSelectable = true
            input.isBezeled = true
            input.isBordered = true
            input.drawsBackground = true
            input.focusRingType = .default
            root.addSubview(input)
            fields.append(input)
        }

        let buttonY: CGFloat = 18
        addButton(
            title: "Exit review",
            frame: NSRect(x: 20, y: buttonY, width: 104, height: 32),
            action: #selector(exitReview),
            root: root
        )
        addButton(
            title: "Skip file",
            frame: NSRect(x: contentWidth - 230, y: buttonY, width: 96, height: 32),
            action: #selector(skipFile),
            root: root
        )
        addButton(
            title: "Save",
            frame: NSRect(x: contentWidth - 122, y: buttonY, width: 102, height: 32),
            action: #selector(save),
            root: root
        )

        self.window = window
    }

    private func addButton(title: String, frame: NSRect, action: Selector, root: NSView) {
        let button = NSButton(title: title, target: self, action: action)
        button.bezelStyle = .rounded
        button.frame = frame
        root.addSubview(button)
    }

    private func measuredHeight(_ text: String, width: CGFloat, font: NSFont) -> CGFloat {
        let rect = NSString(string: text).boundingRect(
            with: NSSize(width: width, height: .greatestFiniteMagnitude),
            options: [.usesLineFragmentOrigin, .usesFontLeading],
            attributes: [.font: font]
        )
        return max(42, ceil(rect.height) + 4)
    }

    private func finish(action: String) {
        result = ReviewResult(
            action: action,
            values: fields.map { $0.stringValue.trimmingCharacters(in: .whitespacesAndNewlines) }
        )
        if let window {
            NSApp.stopModal(withCode: .OK)
            window.close()
        }
    }

    @objc private func save() {
        finish(action: "save")
    }

    @objc private func skipFile() {
        finish(action: "skip")
    }

    @objc private func exitReview() {
        finish(action: "exit")
    }
}

func fail(_ message: String) -> Never {
    FileHandle.standardError.write(Data((message + "\n").utf8))
    exit(1)
}

let inputData = FileHandle.standardInput.readDataToEndOfFile()
guard !inputData.isEmpty else {
    fail("Missing review dialog payload")
}

let payload: ReviewPayload
do {
    payload = try JSONDecoder().decode(ReviewPayload.self, from: inputData)
} catch {
    fail("Invalid review dialog payload: \(error)")
}

let app = NSApplication.shared
let dialog = ReviewDialog(payload: payload)
let result = dialog.run()

do {
    let data = try JSONEncoder().encode(result)
    FileHandle.standardOutput.write(data)
    FileHandle.standardOutput.write(Data("\n".utf8))
} catch {
    fail("Could not encode review result: \(error)")
}
