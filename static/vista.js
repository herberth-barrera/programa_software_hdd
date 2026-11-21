// Vista previa de PDF en una ventana flotante, sin salir de la página.
(function () {
  var ventana = document.getElementById("vista");
  var marco = document.getElementById("vista-marco");
  var titulo = document.getElementById("vista-titulo");
  if (!ventana) return;

  document.addEventListener("click", function (ev) {
    var boton = ev.target.closest("[data-ver]");
    if (!boton) return;
    titulo.textContent = boton.dataset.titulo || "Vista previa";
    marco.src = boton.dataset.ver;
    ventana.showModal();
  });

  function cerrar() {
    ventana.close();
    marco.src = "about:blank";
  }
  document.getElementById("vista-cerrar").addEventListener("click", cerrar);
  ventana.addEventListener("cancel", function () { marco.src = "about:blank"; });
  // Clic fuera de la ventana también cierra
  ventana.addEventListener("click", function (ev) {
    if (ev.target === ventana) cerrar();
  });
})();
