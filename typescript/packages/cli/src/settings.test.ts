// ========= Copyright 2026 @ Strukto.AI All Rights Reserved. =========
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.
// ========= Copyright 2026 @ Strukto.AI All Rights Reserved. =========

import { mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'
import {
  DEFAULT_DAEMON_URL,
  getConfig,
  listConfig,
  loadDaemonSettings,
  setConfig,
  unsetConfig,
} from './settings.ts'

const ABSENT_FILE = '/nonexistent/auth_token'

describe('loadDaemonSettings', () => {
  it('returns defaults when env unset and no file', () => {
    const s = loadDaemonSettings({
      env: {},
      configPath: '/nonexistent/config.toml',
      tokenFile: ABSENT_FILE,
    })
    expect(s.url).toBe(DEFAULT_DAEMON_URL)
    expect(s.authToken).toBe('')
  })

  it('MIRAGE_DAEMON_URL overrides default', () => {
    const s = loadDaemonSettings({
      env: { MIRAGE_DAEMON_URL: 'http://10.0.0.1:9000' },
      configPath: '/nonexistent/config.toml',
      tokenFile: ABSENT_FILE,
    })
    expect(s.url).toBe('http://10.0.0.1:9000')
  })

  it('MIRAGE_TOKEN populates authToken', () => {
    const s = loadDaemonSettings({
      env: { MIRAGE_TOKEN: 'secret' },
      configPath: '/nonexistent/config.toml',
      tokenFile: ABSENT_FILE,
    })
    expect(s.authToken).toBe('secret')
  })

  it('falls back to token file', () => {
    const dir = mkdtempSync(join(tmpdir(), 'mirage-cli-settings-'))
    try {
      const tokenFile = join(dir, 'auth_token')
      writeFileSync(tokenFile, 'from-file')
      const s = loadDaemonSettings({
        env: {},
        configPath: '/nonexistent/config.toml',
        tokenFile,
      })
      expect(s.authToken).toBe('from-file')
    } finally {
      rmSync(dir, { recursive: true, force: true })
    }
  })

  it('reads the exact configPath even when the basename is not config.toml', () => {
    const dir = mkdtempSync(join(tmpdir(), 'mirage-cli-settings-'))
    try {
      const configPath = join(dir, 'custom.toml')
      writeFileSync(configPath, '[daemon]\nurl = "http://127.0.0.1:8888"\n')
      const s = loadDaemonSettings({ env: {}, configPath, tokenFile: ABSENT_FILE })
      expect(s.url).toBe('http://127.0.0.1:8888')
    } finally {
      rmSync(dir, { recursive: true, force: true })
    }
  })

  it('reads config.toml and token file under MIRAGE_HOME', () => {
    const dir = mkdtempSync(join(tmpdir(), 'mirage-cli-settings-'))
    try {
      writeFileSync(join(dir, 'config.toml'), '[daemon]\nurl = "http://127.0.0.1:9999"\n')
      writeFileSync(join(dir, 'auth_token'), 'home-token')
      const s = loadDaemonSettings({ env: { MIRAGE_HOME: dir } })
      expect(s.url).toBe('http://127.0.0.1:9999')
      expect(s.authToken).toBe('home-token')
    } finally {
      rmSync(dir, { recursive: true, force: true })
    }
  })
})

describe('config writer', () => {
  function tmpConfigPath(): { dir: string; path: string } {
    const dir = mkdtempSync(join(tmpdir(), 'mirage-cli-config-'))
    return { dir, path: join(dir, 'config.toml') }
  }

  it('setConfig creates the file and [daemon] header when missing', () => {
    const { dir, path } = tmpConfigPath()
    try {
      setConfig('url', 'http://127.0.0.1:9000', path)
      const text = readFileSync(path, 'utf-8')
      expect(text).toBe('[daemon]\nurl = "http://127.0.0.1:9000"\n')
      expect(getConfig('url', path)).toBe('http://127.0.0.1:9000')
    } finally {
      rmSync(dir, { recursive: true, force: true })
    }
  })

  it('setConfig updates an existing key in place without duplicating', () => {
    const { dir, path } = tmpConfigPath()
    try {
      writeFileSync(path, '[daemon]\nurl = "http://old:1"\n')
      setConfig('url', 'http://new:2', path)
      const text = readFileSync(path, 'utf-8')
      expect(text).toBe('[daemon]\nurl = "http://new:2"\n')
    } finally {
      rmSync(dir, { recursive: true, force: true })
    }
  })

  it('setConfig preserves comments and unrelated keys, appending inside [daemon]', () => {
    const { dir, path } = tmpConfigPath()
    try {
      writeFileSync(
        path,
        '# a comment\n[daemon]\n# keep me\nurl = "http://old:1"\n\n[other]\nfoo = "bar"\n',
      )
      setConfig('auth_token', 'secret', path)
      const text = readFileSync(path, 'utf-8')
      expect(text).toBe(
        '# a comment\n[daemon]\n# keep me\nurl = "http://old:1"\n\nauth_token = "secret"\n[other]\nfoo = "bar"\n',
      )
    } finally {
      rmSync(dir, { recursive: true, force: true })
    }
  })

  it('numeric idle_grace_seconds is written bare (unquoted)', () => {
    const { dir, path } = tmpConfigPath()
    try {
      setConfig('idle_grace_seconds', '45', path)
      const text = readFileSync(path, 'utf-8')
      expect(text).toBe('[daemon]\nidle_grace_seconds = 45\n')
    } finally {
      rmSync(dir, { recursive: true, force: true })
    }
  })

  it('string values escape backslashes and quotes', () => {
    const { dir, path } = tmpConfigPath()
    try {
      setConfig('auth_token', 'a\\b"c', path)
      const text = readFileSync(path, 'utf-8')
      expect(text).toBe('[daemon]\nauth_token = "a\\\\b\\"c"\n')
    } finally {
      rmSync(dir, { recursive: true, force: true })
    }
  })

  it('unsetConfig removes the key', () => {
    const { dir, path } = tmpConfigPath()
    try {
      writeFileSync(path, '[daemon]\nurl = "http://old:1"\nauth_token = "secret"\n')
      unsetConfig('url', path)
      expect(getConfig('url', path)).toBeUndefined()
      expect(getConfig('auth_token', path)).toBe('secret')
    } finally {
      rmSync(dir, { recursive: true, force: true })
    }
  })

  it('unsetConfig is a no-op when the file is absent', () => {
    const { dir, path } = tmpConfigPath()
    try {
      expect(() => {
        unsetConfig('url', path)
      }).not.toThrow()
    } finally {
      rmSync(dir, { recursive: true, force: true })
    }
  })

  it('listConfig returns every written key', () => {
    const { dir, path } = tmpConfigPath()
    try {
      setConfig('url', 'http://127.0.0.1:9000', path)
      setConfig('idle_grace_seconds', '10', path)
      expect(listConfig(path)).toEqual({
        url: 'http://127.0.0.1:9000',
        idle_grace_seconds: '10',
      })
    } finally {
      rmSync(dir, { recursive: true, force: true })
    }
  })

  it('listConfig returns {} when the file is absent', () => {
    const { dir, path } = tmpConfigPath()
    try {
      expect(listConfig(path)).toEqual({})
    } finally {
      rmSync(dir, { recursive: true, force: true })
    }
  })

  it('getConfig returns undefined when the key is unset', () => {
    const { dir, path } = tmpConfigPath()
    try {
      setConfig('url', 'http://127.0.0.1:9000', path)
      expect(getConfig('auth_token', path)).toBeUndefined()
    } finally {
      rmSync(dir, { recursive: true, force: true })
    }
  })

  it('rejects a key outside ALLOWED_KEYS', () => {
    const { dir, path } = tmpConfigPath()
    try {
      expect(() => {
        setConfig('MIRAGE_HOME', '/tmp', path)
      }).toThrow(/unknown config key/)
      expect(() => {
        getConfig('MIRAGE_HOME', path)
      }).toThrow(/unknown config key/)
      expect(() => {
        unsetConfig('MIRAGE_HOME', path)
      }).toThrow(/unknown config key/)
    } finally {
      rmSync(dir, { recursive: true, force: true })
    }
  })
})
