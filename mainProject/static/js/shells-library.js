const categoryFilters = document.querySelectorAll('[data-category-filter]');
const shellCategories = document.querySelectorAll('[data-shell-category]');

categoryFilters.forEach((filter) => {
	filter.addEventListener('click', () => {
		const selectedCategory = filter.dataset.categoryFilter;

		categoryFilters.forEach((categoryFilter) => {
			const isActive = categoryFilter === filter;
			categoryFilter.classList.toggle('is-active', isActive);
			categoryFilter.setAttribute('aria-pressed', String(isActive));
		});

		shellCategories.forEach((category) => {
			category.hidden = selectedCategory !== 'all'
				&& category.dataset.shellCategory !== selectedCategory;
		});
	});
});
