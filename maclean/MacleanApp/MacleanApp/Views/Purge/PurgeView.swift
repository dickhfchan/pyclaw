import SwiftUI

struct PurgeView: View {
    @State private var vm = PurgeViewModel()
    @State private var showConfirm = false

    var body: some View {
        VStack(spacing: 0) {
            HStack {
                Text("Purge")
                    .font(.largeTitle.bold())
                Spacer()
                if vm.state == .scanning {
                    ProgressView().scaleEffect(0.7)
                }
                Button("Scan for Artifacts") {
                    Task { await vm.scan() }
                }
                .buttonStyle(.borderedProminent)
                .disabled(vm.state == .scanning || vm.state == .executing)
            }
            .padding(.horizontal, 24)
            .padding(.top, 20)
            .padding(.bottom, 12)

            if let err = vm.errorMessage {
                HStack {
                    Image(systemName: "exclamationmark.triangle.fill").foregroundStyle(.orange)
                    Text(err).font(.callout)
                    Spacer()
                }
                .padding(.horizontal, 24)
                .padding(.bottom, 8)
            }

            Divider()

            if vm.items.isEmpty && vm.state == .idle {
                ContentUnavailableView(
                    "No Artifacts Found",
                    systemImage: "trash.circle",
                    description: Text("Click Scan to find node_modules, dist, and other build artifacts.")
                )
                .frame(maxHeight: .infinity)
            } else {
                List {
                    ForEach(vm.groupedItems, id: \.root) { group in
                        Section(group.root) {
                            ForEach(group.items) { item in
                                PurgeItemRow(item: item) {
                                    vm.toggleItem(item.id)
                                }
                            }
                        }
                    }
                }
                .listStyle(.inset)
            }

            if vm.state == .ready || vm.state == .done {
                Divider()
                HStack {
                    Toggle("Select All", isOn: .init(
                        get: { vm.items.allSatisfy(\.isSelected) },
                        set: { _ in vm.toggleAll() }
                    ))
                    .toggleStyle(.checkbox)

                    Spacer()

                    if !vm.selectedItems.isEmpty {
                        Button("Purge Selected · \(SizeLabel.format(vm.totalSelectedSize))") {
                            showConfirm = true
                        }
                        .buttonStyle(.borderedProminent)
                        .tint(.red)
                        .disabled(vm.state == .executing)
                    }
                }
                .padding(.horizontal, 24)
                .padding(.vertical, 12)
            }

            if vm.showLog {
                Divider()
                LogDrawer(lines: vm.logLines, isShowing: $vm.showLog)
            }
        }
        .sheet(isPresented: $showConfirm) {
            ConfirmationSheet(
                itemCount: vm.selectedItems.count,
                totalBytes: vm.totalSelectedSize,
                actionLabel: "Purge"
            ) {
                Task { await vm.purge() }
            }
        }
    }
}
