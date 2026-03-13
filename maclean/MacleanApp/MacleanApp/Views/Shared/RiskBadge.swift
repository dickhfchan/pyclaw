import SwiftUI

struct RiskBadge: View {
    let risk: RiskLevel

    var body: some View {
        Text(risk.label)
            .font(.caption2.weight(.semibold))
            .padding(.horizontal, 6)
            .padding(.vertical, 2)
            .background(color.opacity(0.15))
            .foregroundStyle(color)
            .clipShape(Capsule())
    }

    private var color: Color {
        switch risk {
        case .low:    return .green
        case .medium: return .orange
        case .high:   return .red
        }
    }
}
