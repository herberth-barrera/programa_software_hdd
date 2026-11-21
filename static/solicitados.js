// Selector de documentos solicitados: contador y botones "marcar todos / desmarcar todos".
document.querySelectorAll("details.selector").forEach(function (caja) {
  var casillas = caja.querySelectorAll('input[name="documentos"]');
  var cuenta = caja.querySelector("[data-cuenta]");

  function actualizar() {
    var marcadas = caja.querySelectorAll('input[name="documentos"]:checked').length;
    cuenta.textContent = marcadas + " de " + casillas.length;
    cuenta.classList.toggle("vacio", marcadas === 0);
  }

  casillas.forEach(function (c) { c.addEventListener("change", actualizar); });
  caja.querySelectorAll("[data-marcar]").forEach(function (b) {
    b.addEventListener("click", function () {
      var marcar = b.getAttribute("data-marcar") === "todos";
      casillas.forEach(function (c) { c.checked = marcar; });
      actualizar();
    });
  });
  actualizar();
});
