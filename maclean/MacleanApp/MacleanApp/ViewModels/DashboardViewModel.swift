import Foundation
import Combine

@Observable
class DashboardViewModel {
    var metrics = SystemMetrics()
    var recentActivity: [String] = []

    private var timer: AnyCancellable?

    init() {
        startPolling()
        loadRecentActivity()
    }

    private func startPolling() {
        timer = Timer.publish(every: 2, on: .main, in: .common)
            .autoconnect()
            .sink { [weak self] _ in
                self?.refresh()
            }
        refresh()
    }

    private func refresh() {
        let cpu = MetricsService.getCPU()
        let (memUsed, memTotal) = MetricsService.getMemory()
        let (diskUsed, diskTotal) = MetricsService.getDisk()
        let battery = MetricsService.getBattery()

        metrics = SystemMetrics(
            cpuUsage: cpu,
            memoryUsed: memUsed,
            memoryTotal: memTotal,
            diskUsed: diskUsed,
            diskTotal: diskTotal,
            batteryLevel: battery
        )
    }

    private func loadRecentActivity() {
        let logPath = NSHomeDirectory() + "/.config/mole/operations.log"
        guard let content = try? String(contentsOfFile: logPath) else {
            recentActivity = ["No Mole activity found."]
            return
        }
        let lines = content.components(separatedBy: "\n").filter { !$0.isEmpty }
        recentActivity = Array(lines.suffix(10))
    }

    func refreshActivity() {
        loadRecentActivity()
    }
}
