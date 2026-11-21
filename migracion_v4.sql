-- ============================================================
--  Migración v4: documentos solicitados por empleado
--  Ejecutar en phpMyAdmin con la base hospital_hdd seleccionada.
--  Es segura: conserva todos los datos y se puede ejecutar más de una vez.
-- ============================================================
-- A partir de esta versión, la tabla expediente significa "documentos que
-- RRHH le solicita a cada empleado": una fila = un documento solicitado.
-- La columna entregado ya no se usa (el checklist sale de los archivos subidos).
--
-- Para no cambiar nada de golpe, todos los empleados existentes quedan con
-- los documentos del catálogo solicitados. RRHH ajusta después, perfil por perfil.
INSERT IGNORE INTO expediente (empleado_id, documento_id, entregado)
SELECT e.id, d.id, 0
  FROM empleados e CROSS JOIN documentos d;
