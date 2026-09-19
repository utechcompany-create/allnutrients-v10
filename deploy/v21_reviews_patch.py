"""Apply verified purchase reviews after V21's existing feature layers."""
from pathlib import Path
from shutil import copyfile

source = Path(__file__).resolve().parent / 'v21_reviews'
copyfile(source/'reviews.py', Path('app/reviews.py'))
for name in ('reviews.js', 'reviews.css', 'admin-reviews.js'):
    copyfile(source/name, Path('static/assets')/name)

def replace(path, old, new):
    file = Path(path)
    text = file.read_text()
    if text.count(old) != 1:
        raise SystemExit(f'Expected one review target in {path}: {old[:90]}')
    file.write_text(text.replace(old, new))

replace('app/main.py', 'app.include_router(admin_events.router)',
        'app.include_router(admin_events.router)\nfrom . import reviews\napp.include_router(reviews.router)')
with Path('requirements.txt').open('a') as requirements:
    requirements.write('\nPillow>=12.3,<13\n')
replace('static/detail.html', '<section id="productInquiry">',
        '<section id="productReviews" class="review-section" aria-label="구매 리뷰"></section><section id="productInquiry">')
replace('static/detail.html', '<a class="btn ghost" href="#productInquiry">',
        '<a class="btn ghost" href="#productReviews">구매 리뷰</a><a class="btn ghost" href="#productInquiry">')
replace('static/mypage.html', '<section class="card return-section"',
        '<section id="myReviews" class="card review-section" aria-label="내 구매 리뷰"></section><section class="card return-section"')
replace('static/mypage.html', '반품·교환 내역 확인</a>`;',
        '반품·교환 내역 확인</a><a class="btn ghost small" href="#myReviews">구매 리뷰 작성·조회</a>`;')
for name in ('detail', 'mypage'):
    replace(f'static/{name}.html', '</head>', '<link rel="stylesheet" href="assets/reviews.css?v=21-reviews-1"></head>')
    replace(f'static/{name}.html', '</body>', '<script src="assets/reviews.js?v=21-reviews-1"></script></body>')

badge = '<span class="work-count" data-work-count="reviews" aria-live="polite">—</span>'
replace('static/admin.html', '<a href="design-studio.html">',
        '<button class="work-menu" data-view="reviews" data-label="구매 리뷰"><span>구매 리뷰</span>'+badge+'</button><a href="design-studio.html">')
replace('static/admin.html', '<section class="view" id="communications">',
        (source/'admin-section.html').read_text()+'<section class="view" id="communications">')
replace('static/admin.html', '</head>', '<link rel="stylesheet" href="assets/reviews.css?v=21-reviews-1"></head>')
replace('static/admin.html', '</body>', '<script src="assets/admin-reviews.js?v=21-reviews-1"></script></body>')
replace('static/admin.html', "else if(q.get('view')==='communications')",
        "else if(q.get('view')==='reviews'){document.querySelector('[data-view=\"reviews\"]').click()}else if(q.get('view')==='communications')")
for name in ('returns-admin', 'design-studio', 'naver-admin'):
    replace(f'static/{name}.html', '</aside>',
            '<a class="work-menu" href="admin.html?view=reviews"><span>구매 리뷰</span>'+badge+'</a></aside>')
for name in ('admin', 'returns-admin', 'design-studio', 'naver-admin'):
    replace(f'static/{name}.html', 'assets/admin-events.js?v=21-events-1', 'assets/admin-events.js?v=21-reviews-1')
print('V21 verified purchase reviews applied')
