import SwiftUI

struct CleanerView: View {
    @State private var vm = CleanerViewModel()
    @State private var showConfirm = false

    var body: some View {
        VStack(spacing: 0) {
            // Toolbar
            HStack {
                Text("Cleaner")
                    .font(.largeTitle.bold())
                Spacer()
                if vm.state == .scanning {
                    ProgressView()
                        .scaleEffect(0.7)
                }
                Button("Scan") {
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

            if vm.categories.isEmpty && vm.state == .idle {
                ContentUnavailableView(
                    "No Scan Results",
                    systemImage: "sparkles",
                    description: Text("Click Scan to analyze your Mac for junk files.")
                )
                .frame(maxHeight: .infinity)
            } else {
                List {
                    ForEach(vm.categories) { cat in
                        CleanCategoryRow(category: cat) {
                            vm.toggleCategory(cat.id)
                        }
                    }
                }
                .listStyle(.inset)
            }

            // Action bar
            if vm.state == .ready || vm.state == .done {
                Divider()
                HStack {
                    if vm.selectedCount > 0 {
                        Text("\(vm.selectedCount) categor\(vm.selectedCount == 1 ? "y" : "ies") selected · \(SizeLabel.format(vm.totalSelectedSize))")
                            .font(.callout)
                            .foregroundStyle(.secondary)
                    } else {
                        Text("No categories selected")
                            .font(.callout)
                            .foregroundStyle(.secondary)
                    }
                    Spacer()
                    Button("Clean Now") {
                        showConfirm = true
                    }
                    .buttonStyle(.borderedProminent)
                    .tint(.red)
                    .disabled(vm.selectedCount == 0 || vm.state == .executing)
                }
                .padding(.horizontal, 24)
                .padding(.vertical, 12)
            }

            // Log drawer
            if vm.showLog {
                Divider()
                LogDrawer(lines: vm.logLines, isShowing: $vm.showLog)
            }
        }
        .sheet(isPresented: $showConfirm) {
            ConfirmationSheet(
                itemCount: vm.selectedCount,
                totalBytes: vm.totalSelectedSize,
                actionLabel: "Clean"
            ) {
                Task { await vm.clean() }
            }
        }
    }
}
