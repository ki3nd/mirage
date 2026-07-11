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

import type { Command } from 'commander'
import { emit, fail } from './output.ts'
import { getConfig, listConfig, setConfig, unsetConfig } from './settings.ts'

export function registerConfigCommands(program: Command): void {
  const config = program
    .command('config')
    .description('Read and write daemon settings in config.toml.')

  config
    .command('list')
    .description('Print the config.toml [daemon] table.')
    .action(() => {
      const table = listConfig()
      emit(table, (d: Record<string, string>) =>
        Object.entries(d)
          .map(([k, v]) => `${k} = ${v}`)
          .join('\n'),
      )
    })

  config
    .command('get')
    .argument('<key>')
    .description('Print one [daemon] key.')
    .action((key: string) => {
      let value: string | undefined
      try {
        value = getConfig(key)
      } catch (e) {
        fail((e as Error).message, 2)
        return
      }
      if (value === undefined) {
        fail(`${key} is not set`, 1)
        return
      }
      emit({ [key]: value }, () => value)
    })

  config
    .command('set')
    .argument('<key>')
    .argument('<value>')
    .description('Write a [daemon] key (path settings apply on next daemon restart).')
    .action((key: string, value: string) => {
      try {
        setConfig(key, value)
      } catch (e) {
        fail((e as Error).message, 2)
        return
      }
      emit({ [key]: value, written: true }, () => `${key} = ${value}`)
    })

  config
    .command('unset')
    .argument('<key>')
    .description('Remove a [daemon] key.')
    .action((key: string) => {
      try {
        unsetConfig(key)
      } catch (e) {
        fail((e as Error).message, 2)
        return
      }
      emit({ [key]: null, unset: true }, () => `unset ${key}`)
    })
}
