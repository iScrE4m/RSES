/**
 * Created by David on 17.05.2017.
 */

const fetchRses = async (apiUrl, method) => {
	return fetch('/rses/api' + apiUrl, {credentials: "include", method: method})
		.then(res => {
			switch (res.status) {
				case 403:
					throw 'Unauthorized request';
				case 404:
					throw 'Not found';
				case 200: case 201: case 202:
					return res.json()
			}
			console.error(res);
			throw 'Unexpected error';
		})
		.then(out => {
			console.debug(method.toUpperCase() + ' ' + apiUrl + ' \n', out);
			return out
		})
};


const fetchRsesCatch = async (apiUrl, method) => {
	return fetchRses(apiUrl, method)
		.catch(err => {
			notifyError(err);
		});
};


const createDeleteButton = function (idAttribute, clickListener) {
	const button = document.createElement("i");
	button.className = "fa fa-trash-o text-danger rses-ab-d rses-ab-table";
	button.setAttribute(idAttribute.name, idAttribute.id);
	button.setAttribute('aria-hidden', 'true');
	button.addEventListener("click", clickListener);
	return button
};

const createEditButton = function (idAttribute, clickListener) {
	let button = document.createElement("i");
	button.className = "fa fa-pencil text-info rses-ab-i rses-ab-table";
	button.setAttribute(idAttribute.name, idAttribute.id);
	button.setAttribute('aria-hidden', 'true');
	button.setAttribute('data-toggle', 'modal');
	button.setAttribute('data-target', '#edit-modal');
	button.addEventListener("click", clickListener);
	return button
};


const notifyBase = function (severity, icon, text) {
	const alert = document.createElement('div');
	alert.className = `alert alert-${severity} alert-dismissable`;
	const closeButton = document.createElement('a');
	closeButton.className = "close";
	closeButton.setAttribute('data-dismiss', 'alert');
	closeButton.setAttribute('aria-label', 'close');
	closeButton.innerHTML = '&times;';
	const strong = document.createElement('strong');
	strong.innerHTML = `<i class="fa fa-${icon}" aria-hidden="true"></i>`;
	alert.appendChild(strong);
	alert.innerHTML += text;
	alert.appendChild(closeButton);
	const alerts = document.getElementById('alerts');
	alerts.appendChild(alert);
	setTimeout(function () {
		alert.style = 'display: none';
	}, 5000)
};


const notifySuccess = function (text) {
	notifyBase('success', 'check', text);
};

const notifyError = function (text) {
	notifyBase('danger', 'cross', text)
};

const tableLoading = function () {
	return `<tr><td colspan="2" align="center"><i class="text-info fa fa-refresh fa-spin fa-2x fa-fw"></i>
									<span class="sr-only">Loading...</span></td></tr>`;
};

const HTMLEntities = [
	['&amp', '&'],
	['&apos', '\''],
	['&lt', '<'],
	['&gt', '>'],
	['&nbsp', ' '],
	['&quot', '"']
];

const decodeHTML = function (text) {

	HTMLEntities.forEach(entity => {
		text = text.replace(new RegExp(entity[0] + ';', 'g'), entity[1]);
	});

	return text;
};

const encodeHTML = function (text) {
	
	HTMLEntities.forEach(entity => {
		text = text.replace(new RegExp(entity[1], 'g'), entity[0] + ';');
	});
	
	return encodeURIComponent(encodeURIComponent(text));
};

const getDistFromBottom = function () {

	const scrollPosition = window.pageYOffset;
	const windowSize = window.innerHeight;
	const bodyHeight = document.body.offsetHeight;

	return Math.max(bodyHeight - (scrollPosition + windowSize), 0);

};