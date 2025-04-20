const users = [];

// Отображаем имя пользователя
window.onload = function() {
    const username = localStorage.getItem('username');
    document.getElementById('username').textContent = username || 'Гость';

    // Устанавливаем начальную страницу
    const role = localStorage.getItem('role');
    if (role === 'taxpayer') {
        showPage('taxes');
    } else {
        showPage('manage-taxes');
    }
};

// Функция для переключения между разделами
function showPage(pageId) {
    const sections = document.querySelectorAll('main > section');
    sections.forEach(section => section.classList.remove('active'));
    
    document.getElementById(pageId).classList.add('active');
}

function login(event) {
    event.preventDefault();
    const username = document.getElementById('login-username').value;
    const password = document.getElementById('login-password').value;

    const user = users.find(u => u.username === username && u.password === password);
    if (user) {
        alert('Вход выполнен успешно!');
        if (user.role === 'taxpayer') {
            window.location.href = 'taxpayer.html';
        } else if (user.role === 'employee') {
            window.location.href = 'employee.html';
        }
    } else {
        alert('Неверное имя пользователя или пароль.');
    }
}

function register(event) {
    event.preventDefault();
    const username = document.getElementById('register-username').value;
    const password = document.getElementById('register-password').value;
    const role = document.getElementById('register-role').value;

    if (users.some(u => u.username === username)) {
        alert('Пользователь с таким именем уже существует.');
    } else {
        users.push({ username, password, role });
        alert('Регистрация успешна!');
        window.location.href = 'index.html';
    }
}

function logout() {
    document.getElementById('taxpayer-menu').style.display = 'none';
    document.getElementById('employee-menu').style.display = 'none';
    showPage('login');
}

// Обработка отправки заявки на льготы
function submitBenefitRequest(event) {
    event.preventDefault();
    
    const description = document.getElementById('benefit-description').value;
    
    if (!description) {
        alert('Пожалуйста, введите описание льготы.');
        return;
    }

    alert('Заявка на льготу отправлена!');
    document.getElementById('benefit-description').value = ''; // Очищаем поле
}

function addTax() {
    const taxName = prompt("Введите название налога:");
    const taxRate = prompt("Введите ставку налога (%):");

    if (taxName && taxRate) {
        const table = document.getElementById("tax-table").getElementsByTagName('tbody')[0];
        const newRow = table.insertRow();
        newRow.innerHTML = `<td>${taxName}</td><td>${taxRate}%</td>
                            <td><button onclick="editTax(${table.rows.length})">Редактировать</button>
                            <button onclick="deleteTax(${table.rows.length})">Удалить</button></td>`;
    } else {
        alert("Пожалуйста, заполните все поля.");
    }
}

function editTax(rowIndex) {
    const table = document.getElementById("tax-table").getElementsByTagName('tbody')[0];
    const row = table.rows[rowIndex - 1];
    const taxName = prompt("Измените название налога:", row.cells[0].innerText);
    const taxRate = prompt("Измените ставку налога (%):", row.cells[1].innerText.replace('%', ''));

    if (taxName && taxRate) {
        row.cells[0].innerText = taxName;
        row.cells[1].innerText = `${taxRate}%`;
    } else {
        alert("Пожалуйста, заполните все поля.");
    }
}

function deleteTax(rowIndex) {
    const table = document.getElementById("tax-table").getElementsByTagName('tbody')[0];
    table.deleteRow(rowIndex - 1);
}
