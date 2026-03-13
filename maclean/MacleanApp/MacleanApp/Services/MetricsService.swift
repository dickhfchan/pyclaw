import Foundation
import Darwin

enum MetricsService {
    // CPU usage (0.0–1.0)
    static func getCPU() -> Double {
        var cpuInfo: processor_info_array_t?
        var numCpuInfo: mach_msg_type_number_t = 0
        var numCPUs: natural_t = 0

        let result = host_processor_info(mach_host_self(), PROCESSOR_CPU_LOAD_INFO, &numCPUs, &cpuInfo, &numCpuInfo)
        guard result == KERN_SUCCESS, let info = cpuInfo else { return 0 }

        var totalUser: Int32 = 0
        var totalSystem: Int32 = 0
        var totalIdle: Int32 = 0

        for i in 0..<Int(numCPUs) {
            let offset = i * Int(CPU_STATE_MAX)
            totalUser   += info[offset + Int(CPU_STATE_USER)]
            totalSystem += info[offset + Int(CPU_STATE_SYSTEM)]
            totalIdle   += info[offset + Int(CPU_STATE_IDLE)]
        }

        vm_deallocate(mach_task_self_, vm_address_t(bitPattern: info), vm_size_t(numCpuInfo) * vm_size_t(MemoryLayout<integer_t>.size))

        let total = totalUser + totalSystem + totalIdle
        guard total > 0 else { return 0 }
        return Double(totalUser + totalSystem) / Double(total)
    }

    // Memory: (used bytes, total bytes)
    static func getMemory() -> (used: Int64, total: Int64) {
        let size = MemoryLayout<vm_statistics64_data_t>.size / MemoryLayout<integer_t>.size
        var vmStats = vm_statistics64_data_t()
        var count = mach_msg_type_number_t(size)

        let result = withUnsafeMutablePointer(to: &vmStats) {
            $0.withMemoryRebound(to: integer_t.self, capacity: size) {
                host_statistics64(mach_host_self(), HOST_VM_INFO64, $0, &count)
            }
        }

        var totalBytes: Int64 = 0
        var totalSize = MemoryLayout<Int64>.size
        sysctlbyname("hw.memsize", &totalBytes, &totalSize, nil, 0)

        guard result == KERN_SUCCESS else { return (0, totalBytes) }

        let pageSize = Int64(vm_kernel_page_size)
        let used = (Int64(vmStats.active_count) + Int64(vmStats.wire_count) + Int64(vmStats.compressor_page_count)) * pageSize
        return (used, totalBytes)
    }

    // Disk: (used bytes, total bytes) for root volume
    static func getDisk() -> (used: Int64, total: Int64) {
        let url = URL(fileURLWithPath: "/")
        guard let values = try? url.resourceValues(forKeys: [.volumeTotalCapacityKey, .volumeAvailableCapacityForImportantUsageKey]) else {
            return (0, 0)
        }
        let total = Int64(values.volumeTotalCapacity ?? 0)
        let avail = Int64(values.volumeAvailableCapacityForImportantUsage ?? 0)
        return (total - avail, total)
    }

    // Battery: 0.0–1.0, or -1 if unavailable
    static func getBattery() -> Double {
        // Use pmset for simplicity; IOKit would require framework linkage setup
        let task = Process()
        task.executableURL = URL(fileURLWithPath: "/usr/bin/pmset")
        task.arguments = ["-g", "batt"]
        let pipe = Pipe()
        task.standardOutput = pipe
        task.standardError = Pipe()
        try? task.run()
        let data = pipe.fileHandleForReading.readDataToEndOfFile()
        task.waitUntilExit()

        guard let output = String(data: data, encoding: .utf8) else { return -1 }

        // "InternalBattery-0 ...;\t87%; ..."
        let pattern = #"(\d+)%"#
        guard let regex = try? NSRegularExpression(pattern: pattern),
              let match = regex.firstMatch(in: output, range: NSRange(output.startIndex..., in: output)),
              let range = Range(match.range(at: 1), in: output) else {
            return -1
        }
        return (Double(output[range]) ?? -100) / 100.0
    }
}
