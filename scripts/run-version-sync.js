/**
 * @license
 * Copyright 2025 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const newVersion = process.argv[2];

if (!newVersion) {
  console.error('ERROR: No version number provided.');
  console.log('Usage: node scripts/run-version-sync.js <new-version>');
  process.exit(1);
}

const filesToUpdate = ['package.json', 'server.json', 'gemini-extension.json'];

const projectRoot = path.join(__dirname, '..');

console.log(`\n🔄 Starting version sync to v${newVersion}...\n`);

let filesProcessed = 0;

filesToUpdate.forEach((file) => {
  const filePath = path.join(projectRoot, file);
  try {
    const fileContent = fs.readFileSync(filePath, 'utf-8');
    const jsonContent = JSON.parse(fileContent);
    const oldVersion = jsonContent.version;
    let updated = false;

    // Update root version property
    if (oldVersion !== undefined) {
      if (oldVersion !== newVersion) {
        console.log(`✅ Updated ${file} (root):`);
        console.log(`   - Before: ${oldVersion}`);
        console.log(`   - After:  ${newVersion}`);
        jsonContent.version = newVersion;
        updated = true;
      } else {
        console.log(`☑️  Skipping ${file} (root):`);
        console.log(`   - Already at version ${oldVersion}.`);
      }
    } else {
      console.warn(`⚠️  Skipping ${file} (root):`);
      console.warn(`   - No "version" field found.`);
    }

    // Special handling for server.json packages array
    if (file === 'server.json' && Array.isArray(jsonContent.packages)) {
      jsonContent.packages.forEach((pkg) => {
        if (pkg.identifier === '@google-cloud/gemini-cloud-assist-mcp') {
          const oldPackageVersion = pkg.version;
          if (
            oldPackageVersion !== undefined &&
            oldPackageVersion !== newVersion
          ) {
            console.log(`✅ Updated ${file} (package: ${pkg.identifier}):`);
            console.log(`   - Before: ${oldPackageVersion}`);
            console.log(`   - After:  ${newVersion}`);
            pkg.version = newVersion;
            updated = true;
          } else if (oldPackageVersion === newVersion) {
            console.log(`☑️  Skipping ${file} (package: ${pkg.identifier}):`);
            console.log(`   - Already at version ${oldPackageVersion}.`);
          }
        }
      });
    }

    if (updated) {
      const updatedContent = JSON.stringify(jsonContent, null, 2) + '\n';
      fs.writeFileSync(filePath, updatedContent, 'utf-8');
    }
  } catch (error) {
    console.error(`❌ Error processing ${file}:`, error);
  }
  filesProcessed++;
  if (filesProcessed < filesToUpdate.length) {
    console.log('---');
  }
});

console.log('\n✨ Version sync complete.\n');
