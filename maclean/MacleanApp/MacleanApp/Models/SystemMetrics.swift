import Foundation

struct SystemMetrics {
    var cpuUsage: Double = 0       // 0.0 – 1.0
    var memoryUsed: Int64 = 0      // bytes
    var memoryTotal: Int64 = 0     // bytes
    var diskUsed: Int64 = 0        // bytes
    var diskTotal: Int64 = 0       // bytes
    var batteryLevel: Double = -1  // 0.0 – 1.0, -1 = no battery

    var cpuPercent: Int { Int(cpuUsage * 100) }
    var memoryFraction: Double { memoryTotal > 0 ? Double(memoryUsed) / Double(memoryTotal) : 0 }
    var diskFraction: Double { diskTotal > 0 ? Double(diskUsed) / Double(diskTotal) : 0 }
}
