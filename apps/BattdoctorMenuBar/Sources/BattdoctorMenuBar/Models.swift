import Foundation

struct MenubarPayload: Decodable {
    let summary: String
    let causes: [DrainCause]
    let primaryCulprit: PrimaryCulprit?
    let expectedRuntimeMin: Double?
    let currentPowerW: Double?
    let batteryHealthPct: Double?
    let usableWh: Double?
    let warnings: [String]
    let snapshot: Snapshot
}

struct PrimaryCulprit: Decodable {
    let name: String
    let detail: String
    let estimatedW: Double?
    let confidence: String
    let severity: Int
}

struct Snapshot: Decodable {
    let battery: BatteryInfo
    let memory: MemoryInfo
    let system: SystemInfo
    let processes: [ProcessSample]
}

struct BatteryInfo: Decodable {
    let percent: Double?
    let powerW: Double?
    let systemPowerW: Double?
    let externalConnected: Bool?
    let charging: Bool?
    let fullyCharged: Bool?
    let cycleCount: Int?
    let healthPercent: Double?
    let temperatureC: Double?
    let timeRemainingMin: Int?
}

struct MemoryInfo: Decodable {
    let totalMb: Double?
    let swapTotalMb: Double?
    let swapUsedMb: Double?
    let compressorMb: Double?
    let pressure: String?
}

struct SystemInfo: Decodable {
    let model: String?
    let chip: String?
    let osVersion: String?
    let loadAvg: [Double]?
}

struct ProcessSample: Decodable, Identifiable {
    let pid: Int
    let name: String
    let cpuPct: Double?
    let rssMb: Double?

    var id: Int { pid }
}

struct DrainCause: Decodable, Identifiable {
    let name: String
    let estimatedW: Double?
    let sharePct: Double?
    let confidence: String
    let evidence: [String]
    let action: String
    let severity: Int

    var id: String { "\(name)-\(severity)-\(confidence)" }
}
