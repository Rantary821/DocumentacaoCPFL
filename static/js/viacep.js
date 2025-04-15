function buscarEndereco() {
    var cep = document.getElementById("cep").value.replace(/\D/g, '');
    if (cep.length !== 8) return;

    fetch("https://viacep.com.br/ws/" + cep + "/json/")
        .then(response => response.json())
        .then(data => {
            document.getElementById("endereco").value = data.logradouro;
            document.getElementById("cidade").value = data.localidade;
        });
}