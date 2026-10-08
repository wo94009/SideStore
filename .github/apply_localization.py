"""Apply display-only settings localization to the matching SideStore source."""
import base64
import difflib
import json
import pathlib
import re
import sys


def literal_end(text, start):
    delimiter = '"""' if text.startswith('"""', start) else '"'
    pos = start + len(delimiter)
    while pos < len(text):
        if text.startswith(delimiter, pos):
            return pos + len(delimiter)
        if text.startswith('\\(', pos):
            pos = balanced_end(text, pos + 1)
        elif text[pos] == '\\':
            pos += 2
        else:
            pos += 1
    raise ValueError('Unterminated Swift string')


def balanced_end(text, start):
    depth, pos = 1, start + 1
    while depth:
        if text[pos] == '"':
            pos = literal_end(text, pos)
            continue
        if text[pos] == '(':
            depth += 1
        elif text[pos] == ')':
            depth -= 1
        pos += 1
    return pos


def code_mask(text):
    mask = list(text)
    pos = 0
    while pos < len(text):
        end = pos
        if text.startswith('//', pos):
            end = text.find('\n', pos)
            if end < 0:
                end = len(text)
        elif text.startswith('/*', pos):
            end = text.index('*/', pos + 2) + 2
        elif text[pos] == '"':
            end = literal_end(text, pos)
        if end > pos:
            mask[pos:end] = ' ' * (end - pos)
            pos = end
        else:
            pos += 1
    return ''.join(mask)


# Only presentation values are selected. User names, identifiers, keys,
# addresses, raw log lines and arbitrary file contents remain unchanged.
PRESENTATION = {
    'title', 'subtitle', 'label', 'message', 'alertMessage', 'headerTitle',
    'displayType', 'typeName', 'displayValidity', 'status', 'failure',
    'option.rawValue', 'option.displayName', 'certType.displayName',
    'team.type.displayName', 'device.type.displayName', 'type.displayName',
    'brief.type', 'req', 'deleteAlertMessage', 'connectionStatus.title',
    'section.title', 'friendly', 'purpose', 'tag', 'mode.displayName',
    'mode.subtitle', 'preset.name', 'error', 'errorMessage',
    'viewModel.statusText', 'viewModel.subStatusText', 'viewModel.importSummaryMessage',
    'viewModel.activeHeaderTitle', 'err.localizedDescription', 'iface.type.rawValue',
    'selectTitle', 'folderSummaryString', 'location.name', 'location.subtitle',
    'viewModel.errorMessage ?? "An unknown error occurred."',
    'viewModel.errorMessage ?? "No servers available."',
    'viewModel.alertMessage ?? ""', 'editDialog?.message ?? ""',
    'validationError ?? "Please check your configuration settings."',
}


def patch_text(text):
    mask = code_mask(text)
    edits = []
    for match in re.finditer(r'\bText\s*\(', mask):
        start = match.end()
        end = balanced_end(text, start - 1) - 1
        expression = text[start:end].strip()
        expression_mask = code_mask(expression)
        # Multi-argument Date/format initializers and existing verbatim text
        # are intentionally excluded.
        depth = 0
        multi = False
        for char in expression_mask:
            if char in '([{':
                depth += 1
            elif char in ')]}':
                depth -= 1
            elif char == ',' and depth == 0:
                multi = True
        if multi or expression.startswith(('verbatim:', 'LocalizedStringKey(', '.init(')):
            continue
        selected = expression.startswith('"') or expression in PRESENTATION
        if '?' in expression and '"' in expression:
            selected = not any(x in expression for x in ('group.name', 'appID.name', 'device.name', 'device.identifier', 'resolvedAddress', 'customAddress', 'value.isEmpty'))
        selected |= expression.startswith(('displayName(for:', 'nameForInterfaceType(', 'BonjourDiscoveryViewModel.portCategory('))
        if selected:
            edits.append((start, end, 'SideStoreSettingsChinese.translate('+expression+')'))
    for start, end, replacement in reversed(edits):
        text = text[:start] + replacement + text[end:]
    return text, len(edits)


def main():
    root = pathlib.Path(sys.argv[1]).resolve()
    payload = pathlib.Path(__file__).with_name('translations.json').read_bytes()
    data = json.loads(payload)
    assert len(data['translations']) > 1500
    helper = '''

// Settings display translations; embedded in the app, without an injected library.
private enum SideStoreSettingsChinese {
    private static let catalog: [String: Any] = {
        let data = Data(base64Encoded: "BASE64")!
        return (try! JSONSerialization.jsonObject(with: data)) as! [String: Any]
    }()
    private static let exact = catalog["translations"] as! [String: String]
    private static let rules: [(NSRegularExpression, String, String)] = {
        let rows = catalog["templates"] as! [[String: String]]
        return rows.compactMap { row in
            guard let regex = try? NSRegularExpression(pattern: row["pattern"]!) else { return nil }
            return (regex, row["replacement"]!, row["prefix"] ?? "")
        }
    }()
    static func translate(_ text: String) -> String {
        if let translated = exact[text] { return translated }
        let range = NSRange(text.startIndex..<text.endIndex, in: text)
        for (regex, replacement, prefix) in rules {
            if !prefix.isEmpty && !text.hasPrefix(prefix) { continue }
            if regex.firstMatch(in: text, range: range) != nil {
                return regex.stringByReplacingMatches(in: text, range: range, withTemplate: replacement)
            }
        }
        return text
    }
}
'''.replace('private enum SideStoreSettingsChinese', 'enum SideStoreSettingsChinese').replace('BASE64', base64.b64encode(payload).decode())
    report, diff = [], []
    for folder in ('SideStore/Views/Settings', 'AltStore/Settings'):
        for path in sorted((root/folder).rglob('*.swift')):
            before = path.read_text(encoding='utf-8')
            assert 'SideStoreSettingsChinese' not in before, 'Already patched'
            after, count = patch_text(before)
            if path.name == 'HealthCheckView.swift':
                after += helper
            if after != before:
                path.write_text(after, encoding='utf-8', newline='\n')
                name = path.relative_to(root).as_posix()
                report.append({'file': name, 'text_calls_localized': count})
                diff.extend(difflib.unified_diff(before.splitlines(True), after.splitlines(True), 'a/'+name, 'b/'+name))
    assert len(report) >= 30, report
    (root/'localization-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    (root/'localization.patch').write_text(''.join(diff), encoding='utf-8')
    print('Localized', sum(row['text_calls_localized'] for row in report), 'Text calls in', len(report), 'files')


if __name__ == '__main__':
    main()
