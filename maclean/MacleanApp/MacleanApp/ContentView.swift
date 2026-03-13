import SwiftUI

struct ContentView: View {
    @State private var selection: SidebarItem? = .dashboard

    var body: some View {
        NavigationSplitView {
            SidebarView(selection: $selection)
        } detail: {
            Group {
                switch selection {
                case .dashboard, .none:
                    DashboardView()
                case .cleaner:
                    CleanerView()
                case .diskAnalyzer:
                    DiskAnalyzerView()
                case .optimizer:
                    OptimizerView()
                case .purge:
                    PurgeView()
                }
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
        }
        .navigationSplitViewStyle(.balanced)
    }
}
