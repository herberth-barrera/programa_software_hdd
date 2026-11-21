-- Migración v3: acceso por roles, datos personales e historial de cambios.
-- Conserva los datos existentes. Pensada para MariaDB (XAMPP) y para ejecutarse una sola vez
-- desde phpMyAdmin (base hospital_hdd seleccionada, pestaña Importar o SQL).
USE hospital_hdd;
SET NAMES utf8mb4;

-- 1. Datos personales que completa el empleado
ALTER TABLE empleados
    ADD COLUMN IF NOT EXISTS fecha_nacimiento DATE NULL,
    ADD COLUMN IF NOT EXISTS estado_civil VARCHAR(20) NULL,
    ADD COLUMN IF NOT EXISTS direccion VARCHAR(255) NULL;

-- 2. Cuentas de los empleados (se crean solas al primer ingreso o al registrar al empleado)
CREATE TABLE IF NOT EXISTS usuarios (
    id INT AUTO_INCREMENT PRIMARY KEY,
    empleado_id INT NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    debe_cambiar TINYINT NOT NULL DEFAULT 1,
    intentos_fallidos INT NOT NULL DEFAULT 0,
    bloqueado_hasta DATETIME NULL,
    ultimo_acceso DATETIME NULL,
    FOREIGN KEY (empleado_id) REFERENCES empleados(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 3. Historial de cambios por perfil
CREATE TABLE IF NOT EXISTS historial_cambios (
    id INT AUTO_INCREMENT PRIMARY KEY,
    empleado_id INT NOT NULL,
    lote VARCHAR(32) NOT NULL,
    actor VARCHAR(150) NOT NULL,
    rol_actor VARCHAR(10) NOT NULL,
    tipo VARCHAR(20) NOT NULL,
    campo VARCHAR(100) NOT NULL,
    valor_anterior TEXT NULL,
    valor_nuevo TEXT NULL,
    fecha DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_historial_empleado (empleado_id, fecha),
    FOREIGN KEY (empleado_id) REFERENCES empleados(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 4. El checklist ahora refleja los archivos realmente subidos
UPDATE expediente x
   SET x.entregado = (SELECT COUNT(*) > 0 FROM archivos a
                       WHERE a.empleado_id = x.empleado_id AND a.documento_id = x.documento_id);
