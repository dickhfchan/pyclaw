import SwiftUI

struct CleanCategoryRow: View {
    let category: CleanCategory
    let onToggle: () -> Void

    var body: some View {
        HStack(spacing: 12) {
            Toggle("", isOn: .init(get: { category.isSelected }, set: { _ in onToggle() }))
                .labelsHidden()
                .toggleStyle(.checkbox)

            VStack(alignment: .leading, spacing: 2) {
                Text(category.name)
                    .font(.body.weight(.medium))
                Text("\(category.items.count) item\(category.items.count == 1 ? "" : "s")")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            Spacer()

            RiskBadge(risk: category.risk)

            SizeLabel(bytes: category.totalSize, font: .body.weight(.semibold), color: .primary)
        }
        .padding(.vertical, 6)
        .contentShape(Rectangle())
        .onTapGesture { onToggle() }
    }
}
