// main.js
$(document).ready(function(){
    console.log("Js is working 2")
})   

document.addEventListener('DOMContentLoaded', function () {
    const themeToggle = document.getElementById('theme-toggle');
    const body = document.getElementById('theme');

    themeToggle.addEventListener('click', function () {
        if (body.classList.contains('light-mode')) {
            body.classList.remove('light-mode');
            localStorage.setItem('theme', 'dark');
        } else {
            body.classList.add('light-mode');
            localStorage.setItem('theme', 'light');
        }
    });

    // Load theme from local storage
    if (localStorage.getItem('theme') === 'light') {
        body.classList.add('light-mode');
    }
    
});

function showLoading() {
    document.getElementById('loading').style.display = 'block';
    document.getElementById('results').style.display = 'none';
    
    const texts = [
        "This might take a while depending on how many observations there are",
        "Please wait, fetching data...",
        "Almost there, hang tight...",
    ];
    let index = 0;

    setInterval(() => {
        index = (index + 1) % texts.length;
        document.getElementById('loading-text').innerText = texts[index];
    }, 2000);  // Change text every 2 seconds
}
