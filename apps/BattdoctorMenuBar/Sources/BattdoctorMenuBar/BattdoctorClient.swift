import AppKit
import Foundation

enum BattdoctorError: LocalizedError {
    case binaryNotFound
    case failed(String)

    var errorDescription: String? {
        switch self {
        case .binaryNotFound:
            return "battdoctor CLI not found. Run `uv sync` in the repo or set BATTDOCTOR_BIN."
        case .failed(let message):
            return message.isEmpty ? "battdoctor failed." : message
        }
    }
}

enum BattdoctorClient {
    static func binaryURL() -> URL? {
        let fileManager = FileManager.default
        if let env = ProcessInfo.processInfo.environment["BATTDOCTOR_BIN"],
           fileManager.isExecutableFile(atPath: env) {
            return URL(fileURLWithPath: env)
        }

        var candidates: [String] = []
        if let repo = ProcessInfo.processInfo.environment["BATTDOCTOR_REPO"] {
            candidates.append("\(repo)/.venv/bin/battdoctor")
        }

        let bundleRoot = Bundle.main.bundleURL
            .deletingLastPathComponent()
            .deletingLastPathComponent()
        candidates.append(bundleRoot.appendingPathComponent(".venv/bin/battdoctor").path)
        candidates.append("\(NSHomeDirectory())/Documents/code/battdoctor/.venv/bin/battdoctor")
        candidates.append("/opt/homebrew/bin/battdoctor")
        candidates.append("\(NSHomeDirectory())/.local/bin/battdoctor")

        return candidates
            .first(where: { fileManager.isExecutableFile(atPath: $0) })
            .map(URL.init(fileURLWithPath:))
    }

    static func snapshot() throws -> MenubarPayload {
        guard let binary = binaryURL() else {
            throw BattdoctorError.binaryNotFound
        }

        let process = Process()
        process.executableURL = binary
        process.arguments = ["snapshot", "--json", "--lite"]

        let stdout = Pipe()
        let stderr = Pipe()
        process.standardOutput = stdout
        process.standardError = stderr

        try process.run()
        let output = stdout.fileHandleForReading.readDataToEndOfFile()
        let errorOutput = stderr.fileHandleForReading.readDataToEndOfFile()
        process.waitUntilExit()

        guard process.terminationStatus == 0 else {
            let message = String(data: errorOutput, encoding: .utf8) ?? ""
            throw BattdoctorError.failed(message.trimmingCharacters(in: .whitespacesAndNewlines))
        }

        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        return try decoder.decode(MenubarPayload.self, from: output)
    }

    static func copySummary(_ payload: MenubarPayload) {
        let battery = payload.snapshot.battery
        let memory = payload.snapshot.memory
        var lines: [String] = []
        lines.append("battdoctor summary")
        lines.append("Battery: \(Int((battery.percent ?? 0).rounded()))% · health \(Int((battery.healthPercent ?? 0).rounded()))% · \(battery.cycleCount ?? 0) cycles")
        lines.append("Power: \(payload.currentPowerW.map { String(format: "%.1f W", $0) } ?? "unknown")")
        lines.append("Memory pressure: \(memory.pressure ?? "unknown") · swap \(Int(memory.swapUsedMb ?? 0)) MB")
        lines.append("")
        for cause in payload.causes.prefix(5) {
            lines.append("• \(cause.name) [\(cause.confidence)]")
            if let evidence = cause.evidence.first {
                lines.append("  \(evidence)")
            }
            if !cause.action.isEmpty {
                lines.append("  Action: \(cause.action)")
            }
        }
        let text = lines.joined(separator: "\n")
        NSPasteboard.general.clearContents()
        NSPasteboard.general.setString(text, forType: .string)
    }
}
