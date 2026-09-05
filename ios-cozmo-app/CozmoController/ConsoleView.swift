import SwiftUI

struct ConsoleView: View {
    @EnvironmentObject var cozmo: CozmoManager
    @State private var input: String = ""

    var body: some View {
        VStack(spacing: 0) {
            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 2) {
                        ForEach(Array(cozmo.log.enumerated()), id: \.offset) { i, line in
                            Text(line)
                                .font(.system(.caption, design: .monospaced))
                                .foregroundColor(.green)
                                .id(i)
                        }
                    }
                    .padding(8)
                    .frame(maxWidth: .infinity, alignment: .leading)
                }
                .onChange(of: cozmo.log.count) { _ in
                    if let last = cozmo.log.indices.last {
                        withAnimation {
                            proxy.scrollTo(last, anchor: .bottom)
                        }
                    }
                }
            }
            .background(Color.black)

            HStack {
                TextField("forward / lights green / raw coz...", text: $input)
                    .textFieldStyle(.roundedBorder)
                    .autocapitalization(.none)
                    .disableAutocorrection(true)
                    .onSubmit(runInput)
                Button("Run") { runInput() }
                    .buttonStyle(CozmoButtonStyle(color: CozmoTheme.blue))
                    .frame(width: 90)
            }
            .padding(8)
        }
        .background(CozmoTheme.background.ignoresSafeArea())
    }

    private func runInput() {
        ConsoleCommand.run(input, on: cozmo)
        input = ""
    }
}

/// A tiny command language for the console box — typed shorthand for the
/// same actions the Controller tab's buttons trigger, plus a "raw" escape
/// hatch for sending hand-crafted protocol frames while debugging.
enum ConsoleCommand {
    static func run(_ raw: String, on cozmo: CozmoManager) {
        let text = raw.trimmingCharacters(in: .whitespaces).lowercased()
        guard !text.isEmpty else { return }
        let parts = text.split(separator: " ").map(String.init)

        switch parts.first {
        case "forward", "fwd": cozmo.drive(.forward)
        case "backward", "back": cozmo.drive(.backward)
        case "left": cozmo.turn(.left)
        case "right": cozmo.turn(.right)
        case "stop": cozmo.stopAll()
        case "head":
            switch parts.count > 1 ? parts[1] : "center" {
            case "up": cozmo.turnHead(.up)
            case "down": cozmo.turnHead(.down)
            default: cozmo.turnHead(.center)
            }
        case "lift":
            cozmo.lift(parts.count > 1 && parts[1] == "down" ? .down : .up)
        case "lights":
            cozmo.lights(parts.count > 1 ? parts[1] : "off")
        case "connect": cozmo.connect()
        case "disconnect": cozmo.disconnect()
        case "raw":
            cozmo.sendRaw(hex: parts.dropFirst().joined())
        default:
            cozmo.addLog("Unknown command: \(text) (try: forward, backward, left, right, stop, " +
                          "head up/down/center, lift up/down, lights <color>, connect, disconnect, raw <hex>)")
        }
    }
}
