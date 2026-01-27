/**
 * Deployment Test Configuration
 *
 * These tests run against real remote PostgreSQL instances.
 * All required values must be provided via environment variables.
 */

export interface DeploymentConfig {
    host: string;
    port: number;
    user: string;
    password: string;
    database: string;
    name: string;
}

function getRequiredEnv(name: string): string {
    const value = process.env[name];
    if (!value) {
        throw new Error(`Required environment variable ${name} is not set`);
    }
    return value;
}

function getOptionalEnv(name: string, defaultValue: string): string {
    return process.env[name] || defaultValue;
}

function parsePort(value: string): number {
    const port = parseInt(value, 10);
    if (isNaN(port) || port < 1 || port > 65535) {
        throw new Error(`Invalid port number: ${value}. Must be between 1 and 65535.`);
    }
    return port;
}

export function getDeploymentConfig(): DeploymentConfig {
    return {
        host: getRequiredEnv('DEPLOY_TEST_HOST'),
        port: parsePort(getOptionalEnv('DEPLOY_TEST_PORT', '5432')),
        user: getOptionalEnv('DEPLOY_TEST_USER', 'mcp_test'),
        password: getRequiredEnv('DEPLOY_TEST_PASSWORD'),
        database: getOptionalEnv('DEPLOY_TEST_DATABASE', 'mcp_test'),
        name: getOptionalEnv('DEPLOY_TEST_NAME', 'remote-postgres'),
    };
}

export function validateDeploymentConfig(): void {
    const missing: string[] = [];

    if (!process.env['DEPLOY_TEST_HOST']) {
        missing.push('DEPLOY_TEST_HOST');
    }
    if (!process.env['DEPLOY_TEST_PASSWORD']) {
        missing.push('DEPLOY_TEST_PASSWORD');
    }

    if (missing.length > 0) {
        throw new Error(
            `Missing required environment variables for deployment tests:\n` +
            missing.map(v => `  - ${v}`).join('\n') +
            `\n\nSet these variables or use scripts/run-deployment-tests.sh`
        );
    }

    // Validate port if provided
    const portStr = process.env['DEPLOY_TEST_PORT'];
    if (portStr) {
        parsePort(portStr);
    }
}

// Lazy-loaded config to defer validation until tests actually run
let _config: DeploymentConfig | null = null;

export const deploymentConfig: DeploymentConfig = new Proxy({} as DeploymentConfig, {
    get(_target, prop: keyof DeploymentConfig) {
        if (!_config) {
            _config = getDeploymentConfig();
        }
        return _config[prop];
    },
});

export function isDeploymentTestEnabled(): boolean {
    return process.env['RUN_DEPLOYMENT_TESTS'] === 'true';
}
