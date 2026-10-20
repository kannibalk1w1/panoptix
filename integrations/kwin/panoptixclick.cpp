// SPDX-License-Identifier: GPL-2.0-or-later
#include <effect/effect.h>
#include <effect/effecthandler.h>
#include <QJsonDocument>
#include <QJsonObject>
#include <QNetworkAccessManager>
#include <QNetworkReply>
#include <QNetworkRequest>
#include <QTimer>

class PanoptixClickEffect : public KWin::Effect
{
    Q_OBJECT
public:
    PanoptixClickEffect()
    {
        connect(&m_poll, &QTimer::timeout, this, &PanoptixClickEffect::poll);
        m_poll.start(1000);
        connect(KWin::effects, &KWin::EffectsHandler::mouseChanged, this,
                [this](const QPointF &position, const QPointF &, Qt::MouseButtons buttons,
                       Qt::MouseButtons previous, Qt::KeyboardModifiers, Qt::KeyboardModifiers) {
            if (!m_active || m_sending || !(buttons & Qt::LeftButton) || (previous & Qt::LeftButton)) {
                return;
            }
            const auto geometry = KWin::effects->virtualScreenGeometry();
            const QJsonObject payload{
                {"x", position.x()}, {"y", position.y()}, {"session_id", m_session},
                {"desktop_geometry", QJsonObject{{"left", geometry.x()}, {"top", geometry.y()},
                                                {"width", geometry.width()}, {"height", geometry.height()}}}
            };
            m_sending = true;
            auto *reply = m_network.post(request("/api/desktop/kwin-click"), QJsonDocument(payload).toJson(QJsonDocument::Compact));
            connect(reply, &QNetworkReply::finished, this, [this, reply] {
                m_sending = false;
                reply->deleteLater();
            });
        });
        poll();
    }

    bool isActive() const override { return false; } // No visual effect or input interception.

private:
    static QNetworkRequest request(const char *path)
    {
        QNetworkRequest request(QUrl(QStringLiteral("http://127.0.0.1:8765") + QString::fromLatin1(path)));
        request.setHeader(QNetworkRequest::ContentTypeHeader, "application/json");
        request.setTransferTimeout(1500);
        return request;
    }

    void poll()
    {
        if (m_polling) {
            return;
        }
        m_polling = true;
        auto *reply = m_network.get(request("/api/desktop/kwin"));
        connect(reply, &QNetworkReply::finished, this, [this, reply] {
            const auto state = QJsonDocument::fromJson(reply->readAll()).object();
            m_active = reply->error() == QNetworkReply::NoError && state.value("active").toBool();
            m_session = state.value("session_id").toString();
            m_polling = false;
            reply->deleteLater();
        });
    }

    QNetworkAccessManager m_network;
    QTimer m_poll;
    QString m_session;
    bool m_active = false;
    bool m_polling = false;
    bool m_sending = false;
};

KWIN_EFFECT_FACTORY(PanoptixClickEffect, "panoptixclick.json")
#include "panoptixclick.moc"
