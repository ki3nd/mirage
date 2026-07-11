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

import { existsSync, readFileSync } from 'node:fs'
import {
  defaultTokenFile,
  mirageHome,
  parseDaemonTable,
  readDaemonTable,
  readTokenFile,
} from '@struktoai/mirage-server'

import { ENV_DAEMON_URL, ENV_TOKEN } from './env.ts'

export const DEFAULT_DAEMON_URL = 'http://127.0.0.1:8765'

export interface DaemonSettings {
  url: string
  authToken: string
  idleGraceSeconds: number
}

export interface LoadOptions {
  env?: Record<string, string | undefined>
  configPath?: string
  tokenFile?: string
}

export function loadDaemonSettings(options: LoadOptions = {}): DaemonSettings {
  const env = options.env ?? (process.env as Record<string, string | undefined>)
  const table =
    options.configPath !== undefined
      ? existsSync(options.configPath)
        ? parseDaemonTable(readFileSync(options.configPath, 'utf-8'))
        : {}
      : readDaemonTable(mirageHome(env))
  const settings: DaemonSettings = {
    url: table.url ?? DEFAULT_DAEMON_URL,
    authToken: table.auth_token ?? '',
    idleGraceSeconds: Number(table.idle_grace_seconds ?? '30'),
  }
  const envUrl = env[ENV_DAEMON_URL]
  if (envUrl !== undefined && envUrl !== '') {
    settings.url = envUrl
  }
  const envToken = env[ENV_TOKEN]
  if (envToken !== undefined && envToken !== '') {
    settings.authToken = envToken
  }
  if (settings.authToken === '') {
    const fileToken = readTokenFile(options.tokenFile ?? defaultTokenFile(env))
    if (fileToken !== undefined && fileToken !== '') {
      settings.authToken = fileToken
    }
  }
  return settings
}
