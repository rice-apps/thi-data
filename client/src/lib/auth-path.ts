/**
 * HTTP path where Better Auth is mounted (Next route + nginx). Keep in sync with
 * `location ~ ^/auth` in nginx.templates/default.conf.template.
 */
export const BETTER_AUTH_BASE_PATH = '/auth' as const;
