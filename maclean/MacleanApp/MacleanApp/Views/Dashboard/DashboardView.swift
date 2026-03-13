import SwiftUI

struct DashboardView: View {
    @State private var vm = DashboardViewModel()

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 24) {
                Text("Dashboard")
                    .font(.largeTitle.bold())
                    .padding(.top, 4)

                LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 16) {
                    MetricCardView(
                        title: "CPU",
                        icon: "cpu",
                        iconColor: .blue,
                        value: "\(vm.metrics.cpuPercent)%",
                        subtitle: "Processor load",
                        fraction: vm.metrics.cpuUsage
                    )
                    MetricCardView(
                        title: "Memory",
                        icon: "memorychip",
                        iconColor: .purple,
                        value: SizeLabel.format(vm.metrics.memoryUsed),
                        subtitle: "of \(SizeLabel.format(vm.metrics.memoryTotal)) used",
                        fraction: vm.metrics.memoryFraction
                    )
                    MetricCardView(
                        title: "Disk",
                        icon: "internaldrive",
                        iconColor: .green,
                        value: SizeLabel.format(vm.metrics.diskUsed),
                        subtitle: "of \(SizeLabel.format(vm.metrics.diskTotal)) used",
                        fraction: vm.metrics.diskFraction
                    )
                    MetricCardView(
                        title: "Battery",
                        icon: vm.metrics.batteryLevel >= 0 ? "battery.75percent" : "bolt.circle",
                        iconColor: batteryColor,
                        value: vm.metrics.batteryLevel >= 0 ? "\(Int(vm.metrics.batteryLevel * 100))%" : "AC",
                        subtitle: vm.metrics.batteryLevel >= 0 ? "Battery level" : "No battery detected",
                        fraction: vm.metrics.batteryLevel
                    )
                }

                VStack(alignment: .leading, spacing: 10) {
                    HStack {
                        Text("Recent Mole Activity")
                            .font(.headline)
                        Spacer()
                        Button("Refresh") { vm.refreshActivity() }
                            .buttonStyle(.borderless)
                            .font(.caption)
                    }
                    if vm.recentActivity.isEmpty {
                        Text("No activity yet.")
                            .foregroundStyle(.secondary)
                            .font(.caption)
                    } else {
                        VStack(alignment: .leading, spacing: 4) {
                            ForEach(vm.recentActivity, id: \.self) { line in
                                Text(line)
                                    .font(.system(.caption, design: .monospaced))
                                    .foregroundStyle(.secondary)
                            }
                        }
                        .padding(12)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .background(.quaternary.opacity(0.5))
                        .clipShape(RoundedRectangle(cornerRadius: 8))
                    }
                }
            }
            .padding(24)
        }
    }

    private var batteryColor: Color {
        guard vm.metrics.batteryLevel >= 0 else { return .blue }
        if vm.metrics.batteryLevel < 0.2 { return .red }
        if vm.metrics.batteryLevel < 0.4 { return .orange }
        return .green
    }
}
