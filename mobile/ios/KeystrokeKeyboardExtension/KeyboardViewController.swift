import UIKit

/// KeyboardViewController — Custom iOS Keyboard Extension
///
/// This keyboard extension functions as a full pass-through keyboard that
/// captures ONLY key timing metadata (dwell times + inter-key intervals).
/// No actual characters are stored, logged, or transmitted.
///
/// The data is shared with the Flutter host app via an App Group shared
/// UserDefaults container, which the main app reads on foreground activation.
///
/// App Group: group.com.neuroguard.app (configured in both targets)

class KeyboardViewController: UIInputViewController {

    // ── Configuration ──────────────────────────────────────────────────────────
    private let appGroupId     = "group.com.neuroguard.app"
    private let sharedDefaults : UserDefaults?

    // ── State ─────────────────────────────────────────────────────────────────
    private var sessionStart   : TimeInterval = 0
    private var lastDownTime   : TimeInterval = 0
    private var keyDownTimes   : [String: TimeInterval] = [:]
    private var dwellTimes     : [Double] = []
    private var ikiValues      : [Double] = []
    private var backspaceCount : Int = 0
    private var totalKeystrokes: Int = 0

    // ── UI keyboard grid ──────────────────────────────────────────────────────
    private let rows: [[String]] = [
        ["q","w","e","r","t","y","u","i","o","p"],
        ["a","s","d","f","g","h","j","k","l"],
        ["⇧","z","x","c","v","b","n","m","⌫"],
        ["123"," ","return"],
    ]

    required init?(coder: NSCoder) {
        sharedDefaults = UserDefaults(suiteName: appGroupId)
        super.init(coder: coder)
    }

    override init(nibName: String?, bundle: Bundle?) {
        sharedDefaults = UserDefaults(suiteName: appGroupId)
        super.init(nibName: nibName, bundle: bundle)
    }

    override func viewDidLoad() {
        super.viewDidLoad()
        buildKeyboard()
        startSession()
    }

    // ── Session lifecycle ─────────────────────────────────────────────────────

    private func startSession() {
        sessionStart    = Date().timeIntervalSince1970
        dwellTimes      = []
        ikiValues       = []
        backspaceCount  = 0
        totalKeystrokes = 0
        keyDownTimes    = [:]
        lastDownTime    = 0
    }

    /// Flush current session data to shared App Group storage and reset.
    private func flushSession() {
        guard ikiValues.count >= 20 else { return } // minimum viable session

        let payload: [String: Any] = [
            "session_start"         : sessionStart,
            "session_end"           : Date().timeIntervalSince1970,
            "key_press_duration_ms" : dwellTimes,
            "inter_key_interval_ms" : ikiValues,
            "backspace_count"       : backspaceCount,
            "total_keystrokes"      : totalKeystrokes,
            "app_context"           : "other",
        ]

        // Append to pending sessions array
        var pending = sharedDefaults?.array(forKey: "pending_keystroke_sessions") as? [[String: Any]] ?? []
        if pending.count >= 200 { pending.removeFirst() } // cap queue
        pending.append(payload)
        sharedDefaults?.set(pending, forKey: "pending_keystroke_sessions")
        sharedDefaults?.synchronize()

        startSession()
    }

    // ── Keyboard event processing ─────────────────────────────────────────────

    private func handleKeyDown(label: String) {
        let nowMs = Date().timeIntervalSince1970 * 1000
        keyDownTimes[label] = nowMs

        if lastDownTime > 0 {
            let iki = nowMs - lastDownTime
            if iki > 0 && iki < 5000 {
                ikiValues.append(iki)
            }
        }
        lastDownTime = nowMs
        totalKeystrokes += 1
        if label == "⌫" { backspaceCount += 1 }
    }

    private func handleKeyUp(label: String) {
        guard let downMs = keyDownTimes.removeValue(forKey: label) else { return }
        let nowMs = Date().timeIntervalSince1970 * 1000
        let dwell = nowMs - downMs
        if dwell > 0 && dwell < 2000 {
            dwellTimes.append(dwell)
        }

        // Actually insert the character
        if label == "⌫" {
            textDocumentProxy.deleteBackward()
        } else if label == "return" {
            textDocumentProxy.insertText("\n")
        } else {
            textDocumentProxy.insertText(label)
        }

        // Flush after 5 min of accumulated data
        if ikiValues.count >= 300 { flushSession() }
    }

    // ── Keyboard UI ───────────────────────────────────────────────────────────

    private func buildKeyboard() {
        let stack = UIStackView()
        stack.axis        = .vertical
        stack.spacing     = 8
        stack.translatesAutoresizingMaskIntoConstraints = false
        view.addSubview(stack)
        NSLayoutConstraint.activate([
            stack.leadingAnchor .constraint(equalTo: view.leadingAnchor,  constant: 4),
            stack.trailingAnchor.constraint(equalTo: view.trailingAnchor, constant: -4),
            stack.topAnchor     .constraint(equalTo: view.topAnchor,      constant: 8),
            stack.bottomAnchor  .constraint(equalTo: view.bottomAnchor,   constant: -8),
        ])

        for row in rows {
            let rowStack = UIStackView()
            rowStack.axis         = .horizontal
            rowStack.spacing      = 5
            rowStack.distribution = .fillEqually
            for key in row {
                let btn = makeKeyButton(label: key)
                rowStack.addArrangedSubview(btn)
            }
            stack.addArrangedSubview(rowStack)
        }
    }

    private func makeKeyButton(label: String) -> UIButton {
        let btn = UIButton(type: .system)
        btn.setTitle(label == " " ? "space" : label, for: .normal)
        btn.titleLabel?.font      = .systemFont(ofSize: label.count > 1 ? 13 : 17)
        btn.backgroundColor       = label.count > 1
            ? UIColor.systemGray3
            : UIColor.secondarySystemBackground
        btn.layer.cornerRadius    = 5
        btn.layer.shadowColor     = UIColor.black.cgColor
        btn.layer.shadowOpacity   = 0.3
        btn.layer.shadowRadius    = 1
        btn.layer.shadowOffset    = CGSize(width: 0, height: 1)

        btn.addTarget(self, action: #selector(keyDown(_:)), for: .touchDown)
        btn.addTarget(self, action: #selector(keyUp(_:)),   for: [.touchUpInside, .touchUpOutside])
        btn.accessibilityLabel    = label
        return btn
    }

    @objc private func keyDown(_ sender: UIButton) {
        let label = sender.accessibilityLabel ?? ""
        handleKeyDown(label: label)
    }

    @objc private func keyUp(_ sender: UIButton) {
        let label = sender.accessibilityLabel ?? ""
        handleKeyUp(label: label)
    }

    override func viewWillDisappear(_ animated: Bool) {
        super.viewWillDisappear(animated)
        flushSession()
    }
}
