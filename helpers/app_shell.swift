import AppKit
import UniformTypeIdentifiers

func bundlePath(_ components: String...) -> String {
    var url = Bundle.main.bundleURL
    for component in components {
        url.appendPathComponent(component)
    }
    return url.path
}

func runnerPath() -> String {
    bundlePath("Contents", "MacOS", "renamer_cli")
}

func launchWorker(arguments: [String]) -> Int32 {
    let process = Process()
    process.executableURL = URL(fileURLWithPath: runnerPath())
    process.arguments = arguments
    do {
        try process.run()
        process.waitUntilExit()
        return process.terminationStatus
    } catch {
        print(error.localizedDescription)
        return 1
    }
}

let initialArguments = Array(CommandLine.arguments.dropFirst())
if initialArguments == ["--self-test"] {
    print("OK: OSA PDF Renamer app shell is working.")
    exit(0)
}
let openSettingsOnLaunch = initialArguments == ["--settings"]
if initialArguments == ["--about"] {
    exit(launchWorker(arguments: initialArguments))
}
let initialPDFs = initialArguments.filter { $0.lowercased().hasSuffix(".pdf") }
if !initialPDFs.isEmpty {
    exit(launchWorker(arguments: initialPDFs))
}

final class DropZoneView: NSView {
    var onPDFs: (([String]) -> Void)?
    private var isHighlighted = false {
        didSet {
            needsDisplay = true
        }
    }

    override init(frame frameRect: NSRect) {
        super.init(frame: frameRect)
        registerForDraggedTypes([.fileURL])
        wantsLayer = true
    }

    required init?(coder: NSCoder) {
        super.init(coder: coder)
        registerForDraggedTypes([.fileURL])
        wantsLayer = true
    }

    override func draggingEntered(_ sender: NSDraggingInfo) -> NSDragOperation {
        if pdfPaths(from: sender).isEmpty {
            return []
        }
        isHighlighted = true
        return .copy
    }

    override func draggingExited(_ sender: NSDraggingInfo?) {
        isHighlighted = false
    }

    override func performDragOperation(_ sender: NSDraggingInfo) -> Bool {
        isHighlighted = false
        let paths = pdfPaths(from: sender)
        if paths.isEmpty {
            return false
        }
        onPDFs?(paths)
        return true
    }

    override func draw(_ dirtyRect: NSRect) {
        super.draw(dirtyRect)

        let insetBounds = bounds.insetBy(dx: 18, dy: 18)
        let fillPath = NSBezierPath(
            roundedRect: insetBounds,
            xRadius: 14,
            yRadius: 14
        )
        NSColor(calibratedWhite: isHighlighted ? 0.82 : 0.94, alpha: 1).setFill()
        fillPath.fill()

        let dashPath = NSBezierPath(
            roundedRect: insetBounds,
            xRadius: 14,
            yRadius: 14
        )
        dashPath.lineWidth = 2
        dashPath.setLineDash([8, 5], count: 2, phase: 0)
        NSColor.systemBlue.setStroke()
        dashPath.stroke()
    }

    private func pdfPaths(from sender: NSDraggingInfo) -> [String] {
        guard let urls = sender.draggingPasteboard.readObjects(
            forClasses: [NSURL.self],
            options: [.urlReadingFileURLsOnly: true]
        ) as? [URL] else {
            return []
        }

        return urls
            .filter { $0.pathExtension.lowercased() == "pdf" }
            .map { $0.path }
    }
}

struct PresetPayload: Decodable {
    let options: [String]
    let currentPreset: String
    let presets: [PresetInfo]

    enum CodingKeys: String, CodingKey {
        case options
        case currentPreset = "current_preset"
        case presets
    }
}

struct PresetInfo: Decodable {
    let name: String
    let fields: [String]
}

let presetFieldOptions: [(label: String, key: String, defaultEnabled: Bool)] = [
    ("Date", "include_date", true),
    ("Sender", "include_sender", false),
    ("Recipient", "include_recipient", false),
    ("Subject", "include_name", true),
    ("Reference", "include_reference", false),
    ("Document type", "include_type", true),
    ("Amount", "include_amount", false),
    ("Location", "include_location", false),
    ("Status", "include_status", false),
]

let builtInPresets: [PresetInfo] = [
    PresetInfo(name: "General documents", fields: ["Date", "Subject", "Document type"]),
    PresetInfo(name: "Correspondence", fields: ["Date", "Sender", "Subject", "Document type"]),
    PresetInfo(name: "Finance", fields: ["Date", "Sender", "Reference", "Document type", "Amount"]),
    PresetInfo(name: "Legal / case", fields: ["Date", "Subject", "Reference", "Document type"]),
    PresetInfo(name: "Property / site", fields: ["Date", "Location", "Subject", "Document type"]),
    PresetInfo(name: "Logistics", fields: ["Date", "Sender", "Recipient", "Reference", "Document type"]),
    PresetInfo(name: "Full detail", fields: ["Date", "Sender", "Recipient", "Subject", "Reference", "Document type"]),
]

final class AppDelegate: NSObject, NSApplicationDelegate {
    private let bundleURL = Bundle.main.bundleURL
    private var window: NSWindow?
    private var statusLabel = NSTextField(labelWithString: "Ready")
    private var runButton = NSButton()
    private var selectedPaths: [String] = []
    private var pendingOpenPaths: [String] = []

    private var contentsURL: URL {
        bundleURL.appendingPathComponent("Contents")
    }

    private var macOSURL: URL {
        contentsURL.appendingPathComponent("MacOS")
    }

    private var frameworksURL: URL {
        contentsURL.appendingPathComponent("Frameworks")
    }

    private var resourcesURL: URL {
        contentsURL.appendingPathComponent("Resources")
    }

    private var userConfigURL: URL {
        FileManager.default
            .homeDirectoryForCurrentUser
            .appendingPathComponent("Library")
            .appendingPathComponent("Application Support")
            .appendingPathComponent("OSA PDF Renamer")
            .appendingPathComponent("config.toml")
    }

    private var workerPath: String {
        macOSURL.appendingPathComponent("renamer_cli").path
    }

    private var progressRunnerPath: String {
        let frameworkPath = frameworksURL.appendingPathComponent("progress_runner").path
        if FileManager.default.isExecutableFile(atPath: frameworkPath) {
            return frameworkPath
        }
        return resourcesURL.appendingPathComponent("progress_runner").path
    }

    private var version: String {
        let versionURL = resourcesURL.appendingPathComponent("VERSION")
        return (
            try? String(contentsOf: versionURL, encoding: .utf8)
                .trimmingCharacters(in: .whitespacesAndNewlines)
        ) ?? "unknown"
    }

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.regular)
        NSApp.activate(ignoringOtherApps: true)

        if !pendingOpenPaths.isEmpty {
            runHeadlessRename(paths: pendingOpenPaths)
            return
        }

        showWindow()
        if openSettingsOnLaunch {
            DispatchQueue.main.async {
                self.showSettings()
            }
        }
    }

    func application(_ sender: NSApplication, openFiles filenames: [String]) {
        let pdfs = filenames.filter { $0.lowercased().hasSuffix(".pdf") }
        if pdfs.isEmpty {
            sender.reply(toOpenOrPrint: .failure)
            return
        }

        if window == nil {
            pendingOpenPaths.append(contentsOf: pdfs)
        } else {
            runRename(paths: pdfs)
        }
        sender.reply(toOpenOrPrint: .success)
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        true
    }

    private func showWindow() {
        let window = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 520, height: 390),
            styleMask: [.titled, .closable, .miniaturizable],
            backing: .buffered,
            defer: false
        )
        window.title = "OSA PDF Renamer"
        window.isReleasedWhenClosed = false
        window.center()
        window.contentView = buildContent()
        window.makeKeyAndOrderFront(nil)
        self.window = window
    }

    private func buildContent() -> NSView {
        let root = NSView(frame: NSRect(x: 0, y: 0, width: 520, height: 390))

        let title = NSTextField(labelWithString: "Rename PDFs")
        title.font = .systemFont(ofSize: 24, weight: .semibold)
        title.frame = NSRect(x: 28, y: 334, width: 300, height: 30)
        root.addSubview(title)

        let subtitle = NSTextField(labelWithString: "Version \(version)")
        subtitle.font = .systemFont(ofSize: 13)
        subtitle.textColor = .secondaryLabelColor
        subtitle.frame = NSRect(x: 28, y: 308, width: 464, height: 22)
        root.addSubview(subtitle)

        let dropZone = DropZoneView(frame: NSRect(x: 24, y: 104, width: 472, height: 188))
        dropZone.onPDFs = { [weak self] paths in
            self?.addPDFs(paths)
        }
        root.addSubview(dropZone)

        let prompt = NSTextField(labelWithString: "Drop PDFs Here")
        prompt.font = .systemFont(ofSize: 20, weight: .semibold)
        prompt.textColor = NSColor(calibratedWhite: 0.05, alpha: 1)
        prompt.alignment = .center
        prompt.frame = NSRect(x: 44, y: 194, width: 432, height: 28)
        root.addSubview(prompt)

        let detail = NSTextField(labelWithString: "Files are renamed in their current folder.")
        detail.font = .systemFont(ofSize: 13)
        detail.textColor = NSColor(calibratedWhite: 0.16, alpha: 1)
        detail.alignment = .center
        detail.frame = NSRect(x: 44, y: 168, width: 432, height: 22)
        root.addSubview(detail)

        statusLabel.font = .systemFont(ofSize: 12)
        statusLabel.textColor = .secondaryLabelColor
        statusLabel.frame = NSRect(x: 28, y: 70, width: 464, height: 22)
        root.addSubview(statusLabel)

        let chooseButton = NSButton(title: "Choose PDFs...", target: self, action: #selector(choosePDFs))
        chooseButton.bezelStyle = .rounded
        chooseButton.frame = NSRect(x: 28, y: 26, width: 120, height: 32)
        root.addSubview(chooseButton)

        runButton = NSButton(title: "Rename", target: self, action: #selector(renameSelected))
        runButton.bezelStyle = .rounded
        runButton.isEnabled = false
        if #available(macOS 11.0, *) {
            runButton.hasDestructiveAction = false
        }
        runButton.frame = NSRect(x: 156, y: 26, width: 92, height: 32)
        root.addSubview(runButton)

        let settingsButton = NSButton(title: "Presets", target: self, action: #selector(showSettings))
        settingsButton.bezelStyle = .rounded
        settingsButton.frame = NSRect(x: 376, y: 26, width: 92, height: 32)
        root.addSubview(settingsButton)

        return root
    }

    @objc private func choosePDFs() {
        let panel = NSOpenPanel()
        panel.allowsMultipleSelection = true
        panel.canChooseDirectories = false
        panel.canChooseFiles = true
        panel.allowedContentTypes = [.pdf]
        if panel.runModal() == .OK {
            addPDFs(panel.urls.map { $0.path })
        }
    }

    @objc private func renameSelected() {
        runRename(paths: selectedPaths)
    }

    private func addPDFs(_ paths: [String]) {
        let existing = Set(selectedPaths)
        let newPaths = paths
            .filter { $0.lowercased().hasSuffix(".pdf") }
            .filter { !existing.contains($0) }
        selectedPaths.append(contentsOf: newPaths)
        statusLabel.stringValue = "\(selectedPaths.count) PDF file(s) selected"
        updateRenameButton()
    }

    private func clearSelection() {
        selectedPaths.removeAll()
        updateRenameButton()
    }

    private func updateRenameButton() {
        let hasSelection = !selectedPaths.isEmpty
        runButton.isEnabled = hasSelection
        if #available(macOS 11.0, *) {
            runButton.bezelColor = hasSelection ? .systemBlue : nil
        }
    }

    @objc private func showSettings() {
        presentPresetPicker(selectedPreset: nil)
    }

    private func presentPresetPicker(selectedPreset: String?) {
        guard let window else {
            return
        }
        guard let payload = loadPresetPayload() else {
            statusLabel.stringValue = "Could not load presets"
            return
        }

        let currentName = selectedPreset ?? payload.currentPreset
        let popUp = NSPopUpButton(frame: NSRect(x: 0, y: 0, width: 520, height: 28))
        for preset in payload.presets {
            popUp.addItem(withTitle: presetSummary(preset))
        }
        if let selectedIndex = payload.presets.firstIndex(where: { $0.name == currentName }) {
            popUp.selectItem(at: selectedIndex)
        }

        let accessory = NSView(frame: NSRect(x: 0, y: 0, width: 520, height: 30))
        accessory.addSubview(popUp)

        let alert = NSAlert()
        alert.messageText = "Filename presets"
        alert.informativeText = "Choose a preset to edit. Each preset shows the fields it currently enables."
        alert.addButton(withTitle: "Edit")
        alert.addButton(withTitle: "Close")
        alert.accessoryView = accessory
        alert.beginSheetModal(for: window) { [weak self] response in
            guard response == .alertFirstButtonReturn else {
                return
            }
            let index = max(0, popUp.indexOfSelectedItem)
            guard payload.presets.indices.contains(index) else {
                return
            }
            self?.presentPresetFieldsEditor(
                preset: payload.presets[index],
                options: payload.options
            )
        }
    }

    private func presentPresetFieldsEditor(preset: PresetInfo, options: [String]) {
        guard let window else {
            return
        }

        let rowHeight: CGFloat = 30
        let accessory = NSView(
            frame: NSRect(
                x: 0,
                y: 0,
                width: 280,
                height: CGFloat(options.count) * rowHeight
            )
        )
        var checkboxes: [NSButton] = []
        for (index, option) in options.enumerated() {
            let y = CGFloat(options.count - index - 1) * rowHeight
            let checkbox = NSButton(
                checkboxWithTitle: option,
                target: nil,
                action: nil
            )
            checkbox.frame = NSRect(x: 0, y: y, width: 280, height: 24)
            checkbox.state = preset.fields.contains(option) ? .on : .off
            accessory.addSubview(checkbox)
            checkboxes.append(checkbox)
        }

        let alert = NSAlert()
        alert.messageText = "Edit preset: \(preset.name)"
        alert.informativeText = "Choose the fields this preset should include, then save."
        alert.addButton(withTitle: "Save")
        alert.addButton(withTitle: "Cancel")
        alert.accessoryView = accessory
        alert.beginSheetModal(for: window) { [weak self] response in
            guard let self else {
                return
            }
            guard response == .alertFirstButtonReturn else {
                self.presentPresetPicker(selectedPreset: preset.name)
                return
            }

            let selectedFields = zip(options, checkboxes)
                .filter { _, checkbox in checkbox.state == .on }
                .map { option, _ in option }
            guard !selectedFields.isEmpty else {
                self.statusLabel.stringValue = "At least one filename field must be enabled"
                self.presentPresetFieldsEditor(preset: preset, options: options)
                return
            }

            if self.savePreset(name: preset.name, fields: selectedFields) {
                self.statusLabel.stringValue = "Preset saved: \(preset.name)"
            } else {
                self.statusLabel.stringValue = "Could not save preset"
            }
            self.presentPresetPicker(selectedPreset: preset.name)
        }
    }

    private func presetSummary(_ preset: PresetInfo) -> String {
        "\(preset.name) - \(preset.fields.joined(separator: ", "))"
    }

    private func loadPresetPayload() -> PresetPayload? {
        let configText = (
            try? String(contentsOf: userConfigURL, encoding: .utf8)
        ) ?? ""
        let parsed = parseOutputConfig(configText)
        let outputFields = presetFieldOptions
            .filter { parsed.enabled[$0.key] ?? $0.defaultEnabled }
            .map { $0.label }

        var presets = builtInPresets
        presets.append(
            PresetInfo(
                name: "Custom",
                fields: outputFields.isEmpty ? ["Date", "Subject", "Document type"] : outputFields
            )
        )
        for savedPreset in parsed.savedPresets {
            if let index = presets.firstIndex(where: { $0.name == savedPreset.name }) {
                presets[index] = savedPreset
            } else {
                presets.append(savedPreset)
            }
        }

        let current = presets.contains(where: { $0.name == parsed.currentPreset })
            ? parsed.currentPreset
            : "General documents"
        return PresetPayload(
            options: presetFieldOptions.map { $0.label },
            currentPreset: current,
            presets: presets
        )
    }

    private func savePreset(name: String, fields: [String]) -> Bool {
        do {
            let directory = userConfigURL.deletingLastPathComponent()
            try FileManager.default.createDirectory(
                at: directory,
                withIntermediateDirectories: true
            )
            let existing = (
                try? String(contentsOf: userConfigURL, encoding: .utf8)
            ) ?? ""
            let updated = rewriteOutputConfig(
                existing,
                presetName: name,
                fields: fields
            )
            try updated.write(to: userConfigURL, atomically: true, encoding: .utf8)
            return true
        } catch {
            return false
        }
    }

    private func parseOutputConfig(_ text: String) -> (
        currentPreset: String,
        enabled: [String: Bool],
        savedPresets: [PresetInfo]
    ) {
        var section = ""
        var currentPreset = "General documents"
        var enabled: [String: Bool] = [:]
        var savedFieldsByPreset: [String: [String]] = [:]

        for rawLine in text.components(separatedBy: .newlines) {
            let line = rawLine
                .split(separator: "#", maxSplits: 1)
                .first
                .map(String.init)?
                .trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
            if line.isEmpty {
                continue
            }
            if line.hasPrefix("[") && line.hasSuffix("]") {
                section = String(line.dropFirst().dropLast())
                continue
            }
            let parts = line.split(separator: "=", maxSplits: 1).map {
                String($0).trimmingCharacters(in: .whitespacesAndNewlines)
            }
            guard parts.count == 2 else {
                continue
            }

            if section == "output" {
                if parts[0] == "preset" {
                    currentPreset = unquoteToml(parts[1])
                } else if presetFieldOptions.contains(where: { $0.key == parts[0] }) {
                    enabled[parts[0]] = parts[1].lowercased() == "true"
                }
            } else if let presetName = presetName(from: section),
                      parts[0] == "fields" {
                let fields = parseTomlStringArray(parts[1]).filter { field in
                    presetFieldOptions.contains(where: { $0.label == field })
                }
                if !fields.isEmpty {
                    savedFieldsByPreset[presetName] = fields
                }
            }
        }

        let savedPresets = savedFieldsByPreset
            .map { PresetInfo(name: $0.key, fields: $0.value) }
            .sorted { $0.name < $1.name }
        return (currentPreset, enabled, savedPresets)
    }

    private func presetName(from section: String) -> String? {
        let prefix = "output.presets."
        guard section.hasPrefix(prefix) else {
            return nil
        }
        return unquoteToml(String(section.dropFirst(prefix.count)))
    }

    private func rewriteOutputConfig(
        _ existing: String,
        presetName: String,
        fields: [String]
    ) -> String {
        var keptLines: [String] = []
        var skippingOutput = false
        for line in existing.components(separatedBy: .newlines) {
            let trimmed = line.trimmingCharacters(in: .whitespacesAndNewlines)
            if trimmed.hasPrefix("[") && trimmed.hasSuffix("]") {
                let section = String(trimmed.dropFirst().dropLast())
                skippingOutput = section == "output" || section.hasPrefix("output.")
            }
            if !skippingOutput {
                keptLines.append(line)
            }
        }

        while keptLines.last?.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty == true {
            keptLines.removeLast()
        }

        var outputLines = [
            "[output]",
            "preset = \(tomlString(presetName))",
        ]
        for option in presetFieldOptions {
            outputLines.append(
                "\(option.key) = \(fields.contains(option.label) ? "true" : "false")"
            )
        }
        outputLines.append("")
        outputLines.append("[output.presets.\(tomlKey(presetName))]")
        outputLines.append("fields = \(tomlStringArray(fields))")

        return (keptLines + [""] + outputLines).joined(separator: "\n") + "\n"
    }

    private func unquoteToml(_ value: String) -> String {
        let trimmed = value.trimmingCharacters(in: .whitespacesAndNewlines)
        guard trimmed.hasPrefix("\"") && trimmed.hasSuffix("\"") else {
            return trimmed
        }
        let inner = trimmed.dropFirst().dropLast()
        return inner
            .replacingOccurrences(of: "\\\"", with: "\"")
            .replacingOccurrences(of: "\\\\", with: "\\")
    }

    private func parseTomlStringArray(_ value: String) -> [String] {
        var fields: [String] = []
        var current = ""
        var inString = false
        var isEscaped = false
        for character in value {
            if isEscaped {
                current.append(character)
                isEscaped = false
                continue
            }
            if character == "\\" && inString {
                isEscaped = true
                continue
            }
            if character == "\"" {
                if inString {
                    fields.append(current)
                    current = ""
                }
                inString.toggle()
                continue
            }
            if inString {
                current.append(character)
            }
        }
        return fields
    }

    private func tomlKey(_ value: String) -> String {
        let allowed = CharacterSet.alphanumerics.union(CharacterSet(charactersIn: "_-"))
        if value.unicodeScalars.allSatisfy({ allowed.contains($0) }) {
            return value
        }
        return tomlString(value)
    }

    private func tomlString(_ value: String) -> String {
        "\"" + value
            .replacingOccurrences(of: "\\", with: "\\\\")
            .replacingOccurrences(of: "\"", with: "\\\"") + "\""
    }

    private func tomlStringArray(_ values: [String]) -> String {
        "[" + values.map(tomlString).joined(separator: ", ") + "]"
    }

    private func runHeadlessRename(paths: [String]) {
        DispatchQueue.global(qos: .userInitiated).async {
            let status = self.launchRunner(arguments: paths, wait: true)
            DispatchQueue.main.async {
                exit(status)
            }
        }
    }

    private func runRename(paths: [String]) {
        guard !paths.isEmpty else {
            return
        }
        statusLabel.stringValue = "Renaming \(paths.count) PDF file(s)..."
        runButton.isEnabled = false

        DispatchQueue.global(qos: .userInitiated).async {
            let status = self.launchWithProgress(arguments: paths)
            DispatchQueue.main.async {
                if status == 0 {
                    self.statusLabel.stringValue = "Finished"
                    self.clearSelection()
                } else {
                    self.statusLabel.stringValue = "Rename failed or was cancelled"
                    self.updateRenameButton()
                }
            }
        }
    }

    private func launchWithProgress(arguments: [String]) -> Int32 {
        let progressRunner = progressRunnerPath
        if FileManager.default.isExecutableFile(atPath: progressRunner) {
            return launch(
                executable: progressRunner,
                arguments: [
                    "--progress-env",
                    "OSA_PDF_RENAMER_PROGRESS_FILE",
                    "OSA PDF Renamer",
                    "Renaming PDFs",
                    workerPath,
                ] + arguments,
                wait: true
            )
        }
        return launchRunner(arguments: arguments, wait: true)
    }

    private func launchRunner(arguments: [String], wait: Bool) -> Int32 {
        launch(executable: workerPath, arguments: arguments, wait: wait)
    }

    private func launch(executable: String, arguments: [String], wait: Bool) -> Int32 {
        let process = Process()
        process.executableURL = URL(fileURLWithPath: executable)
        process.arguments = arguments
        do {
            try process.run()
            if wait {
                process.waitUntilExit()
                return process.terminationStatus
            }
            return 0
        } catch {
            DispatchQueue.main.async {
                self.statusLabel.stringValue = error.localizedDescription
            }
            return 1
        }
    }
}

let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.run()
