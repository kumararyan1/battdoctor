// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "BattdoctorMenuBar",
    platforms: [.macOS(.v14)],
    targets: [
        .executableTarget(
            name: "BattdoctorMenuBar",
            path: "Sources/BattdoctorMenuBar"
        )
    ]
)
