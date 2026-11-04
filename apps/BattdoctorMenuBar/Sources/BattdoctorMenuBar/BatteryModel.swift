import Combine
import Foundation

final class BatteryModel: ObservableObject {
    @Published var payload: MenubarPayload?
    @Published var error: String?
    @Published var lastUpdated: Date?
    @Published var isRefreshing = false

    var onUpdate: (() -> Void)?
    private var refreshInFlight = false

    func refresh() {
        if refreshInFlight {
            return
        }
        refreshInFlight = true
        isRefreshing = true
        error = nil

        DispatchQueue.global(qos: .utility).async {
            let result = Result { try BattdoctorClient.snapshot() }
            DispatchQueue.main.async {
                switch result {
                case .success(let payload):
                    self.payload = payload
                    self.error = nil
                    self.lastUpdated = Date()
                case .failure(let failure):
                    self.error = failure.localizedDescription
                }
                self.isRefreshing = false
                self.refreshInFlight = false
                self.onUpdate?()
            }
        }
    }
}
