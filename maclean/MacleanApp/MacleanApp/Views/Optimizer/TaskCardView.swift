import SwiftUI

struct TaskCardView: View {
    let task: OptimizeTask
    let onFix: () -> Void

    var body: some View {
        HStack(spacing: 14) {
            Image(systemName: statusIcon)
                .font(.title2)
                .foregroundStyle(statusColor)
                .frame(width: 28)

            VStack(alignment: .leading, spacing: 3) {
                Text(task.name)
                    .font(.body.weight(.medium))
                if !task.description.isEmpty {
                    Text(task.description)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }

            Spacer()

            if task.isFixable && task.status != .pass {
                Button("Fix") { onFix() }
                    .buttonStyle(.bordered)
                    .controlSize(.small)
            }
        }
        .padding(14)
        .background(.background.shadow(.drop(color: .black.opacity(0.05), radius: 4, y: 1)))
        .clipShape(RoundedRectangle(cornerRadius: 10))
    }

    private var statusIcon: String {
        switch task.status {
        case .pass:    return "checkmark.circle.fill"
        case .warning: return "exclamationmark.triangle.fill"
        case .fail:    return "xmark.circle.fill"
        }
    }

    private var statusColor: Color {
        switch task.status {
        case .pass:    return .green
        case .warning: return .orange
        case .fail:    return .red
        }
    }
}
