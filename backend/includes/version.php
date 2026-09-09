<?php
/**
 * StudyHub - build and schema version.
 *
 * This ships WITH the code, so an upgrade migrates itself. config.php also
 * carries SCHEMA_VERSION, but that file belongs to the site owner and is never
 * overwritten by an upgrade — which meant a new build's tables and columns were
 * silently never created. db.php now takes the HIGHER of the two.
 *
 * When schema.php changes, raise APP_SCHEMA_VERSION here. Nothing else to do.
 */

if (!defined('APP_SCHEMA_VERSION')) {
    define('APP_SCHEMA_VERSION', 85);
}
if (!defined('APP_VERSION')) {
    define('APP_VERSION', '23.49');
}
