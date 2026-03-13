import SwiftUI

struct DiskAnalyzerView: View {
    @State private var vm = DiskAnalyzerViewModel()
    @State private var hoveredNode: DiskNode? = nil
    @State private var scanPath = NSHomeDirectory()

    var body: some View {
        VStack(spacing: 0) {
            // Toolbar
            HStack {
                Text("Disk Analyzer")
                    .font(.largeTitle.bold())
                Spacer()
                if vm.state == .scanning {
                    ProgressView().scaleEffect(0.7)
                }
                TextField("Path", text: $scanPath)
                    .textFieldStyle(.roundedBorder)
                    .frame(maxWidth: 220)
                Button("Scan") {
                    Task { await vm.scan(atPath: scanPath) }
                }
                .buttonStyle(.borderedProminent)
                .disabled(vm.state == .scanning)
            }
            .padding(.horizontal, 24)
            .padding(.top, 20)
            .padding(.bottom, 12)

            // Breadcrumb
            if !vm.path.isEmpty {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 4) {
                        ForEach(Array(vm.path.enumerated()), id: \.element.id) { idx, node in
                            Button(node.name) {
                                vm.navigateTo(node)
                            }
                            .buttonStyle(.borderless)
                            .foregroundStyle(idx == vm.path.count - 1 ? .primary : .secondary)
                            if idx < vm.path.count - 1 {
                                Image(systemName: "chevron.right")
                                    .font(.caption)
                                    .foregroundStyle(.tertiary)
                            }
                        }
                    }
                    .padding(.horizontal, 24)
                    .padding(.bottom, 8)
                }
            }

            Divider()

            if vm.state == .idle {
                ContentUnavailableView(
                    "No Data",
                    systemImage: "internaldrive",
                    description: Text("Click Scan to analyze disk usage.")
                )
                .frame(maxHeight: .infinity)
            } else if vm.state == .scanning {
                VStack(spacing: 16) {
                    ProgressView("Scanning disk...")
                }
                .frame(maxHeight: .infinity)
            } else if let current = vm.currentNode {
                if let children = current.children, !children.isEmpty {
                    TreeMapView(node: current) { tapped in
                        vm.drillInto(tapped)
                    }
                    .padding(16)
                } else {
                    ContentUnavailableView(
                        current.name,
                        systemImage: "doc",
                        description: Text(SizeLabel.format(current.size))
                    )
                    .frame(maxHeight: .infinity)
                }
            }

            // Footer
            if let hovered = hoveredNode {
                Divider()
                HStack {
                    Text(hovered.path)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .lineLimit(1)
                        .truncationMode(.middle)
                    Spacer()
                    SizeLabel(bytes: hovered.size, font: .caption.weight(.medium), color: .primary)
                }
                .padding(.horizontal, 24)
                .padding(.vertical, 6)
            }
        }
    }
}
