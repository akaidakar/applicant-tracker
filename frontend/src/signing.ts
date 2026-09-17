// Signs a submission the way the applicant's GitHub Action does, so the
// tester page can show the /submission endpoint accepting a real signature
// and rejecting a wrong one. Runs in the browser with Web Crypto; the secret
// never leaves the page except inside the HMAC.

export type SubmissionPayload = Record<string, string>

// Python's json.dumps(payload, separators=(",", ":"), sort_keys=True) with
// its default ensure_ascii=True: sorted keys, no spaces, non-ASCII escaped
// as \uXXXX. The server hashes exactly these bytes.
export function canonicalJson(payload: SubmissionPayload): string {
  const sorted = Object.fromEntries(Object.entries(payload).sort(([a], [b]) => (a < b ? -1 : 1)))
  return JSON.stringify(sorted).replace(
    /[-￿]/g,
    (c) => '\\u' + c.charCodeAt(0).toString(16).padStart(4, '0'),
  )
}

export async function sign(canonical: string, secret: string): Promise<string> {
  const encoder = new TextEncoder()
  const key = await crypto.subtle.importKey(
    'raw',
    encoder.encode(secret),
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign'],
  )
  const digest = await crypto.subtle.sign('HMAC', key, encoder.encode(canonical))
  const hex = Array.from(new Uint8Array(digest), (b) => b.toString(16).padStart(2, '0')).join('')
  return `sha256=${hex}`
}

// The same request as a shell command, for a reviewer who wants to hit the
// endpoint outside the browser. The secret stays a placeholder.
export function shellSnippet(origin: string, canonical: string): string {
  const body = canonical.replace(/'/g, `'\\''`)
  return [
    `SECRET='<signing secret>'`,
    `BODY='${body}'`,
    `SIG=$(printf '%s' "$BODY" | openssl dgst -sha256 -hmac "$SECRET" | sed 's/^.* //')`,
    `curl -sS -X POST ${origin}/submission \\`,
    `  -H 'Content-Type: application/json' \\`,
    `  -H "X-Signature-256: sha256=$SIG" \\`,
    `  --data-binary "$BODY"`,
  ].join('\n')
}
