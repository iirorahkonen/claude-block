#!/usr/bin/env node
/**
 * Session Start Hook
 * Previously checked for jq installation (no longer needed with Node.js)
 * Now serves as a simple session start hook that always continues.
 */

// Always continue - no dependencies to check with Node.js
console.log(JSON.stringify({ decision: 'continue' }));
process.exit(0);
