import SwiftUI

struct OptimizerView: View {
    @State private var vm = OptimizerViewModel()

    var body: some View {
        VStack(spacing: 0) {
            HStack {
                Text("Optimizer")
                    .font(.largeTitle.bold())
                Spacer()
                if vm.state == .scanning {
                    ProgressView().scaleEffect(0.7)
                }
                Button("Run Checks") {
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
                    Image(systemName: "exclamationmark.triangle.fill")
                        .foregroundStyle(.orange)
                    Text(err)
                        .font(.callout)
                    Spacer()
                }
                .padding(.horizontal, 24)
                .padding(.bottom, 8)
            }

            if !vm.tasks.isEmpty {
                HStack(spacing: 20) {
                    Label("\(vm.passCount) passed", systemImage: "checkmark.circle.fill")
                        .foregroundStyle(.green)
                    Label("\(vm.warnCount) warnings", systemImage: "exclamationmark.triangle.fill")
                        .foregroundStyle(.orange)
                    Label("\(vm.failCount) issues", systemImage: "xmark.circle.fill")
                        .foregroundStyle(.red)
                }
                .font(.caption)
                .padding(.horizontal, 24)
                .padding(.bottom, 8)
            }

            Divider()

            if vm.tasks.isEmpty && vm.state == .idle {
                ContentUnavailableView(
                    "No Checks Run",
                    systemImage: "bolt.circle",
                    description: Text("Click Run Checks to analyze your system.")
                )
                .frame(maxHeight: .infinity)
            } else {
                ScrollView {
                    LazyVStack(spacing: 10) {
                        ForEach(vm.tasks) { task in
                            TaskCardView(task: task) {
                                Task { await vm.fix(task) }
                            }
                        }
                    }
                    .padding(24)
                }
            }

            if vm.showLog {
                Divider()
                LogDrawer(lines: vm.logLines, isShowing: $vm.showLog)
            }
        }
    }
}
